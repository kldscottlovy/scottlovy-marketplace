# Security Review Checklist

Comprehensive security guidelines for reviewing the PIP codebase, based on OWASP Top 10 and common vulnerability patterns.

## OWASP Top 10 Quick Reference

1. **Broken Access Control** - Authorization bypasses, privilege escalation
2. **Cryptographic Failures** - Weak encryption, exposed sensitive data
3. **Injection** - SQL, NoSQL, OS command, LDAP injection
4. **Insecure Design** - Missing security controls, threat modeling gaps
5. **Security Misconfiguration** - Default credentials, verbose errors
6. **Vulnerable Components** - Outdated libraries, unpatched dependencies
7. **Identification and Authentication Failures** - Weak passwords, session management
8. **Software and Data Integrity Failures** - Unsigned code, insecure CI/CD
9. **Security Logging Failures** - Missing logs, inadequate monitoring
10. **Server-Side Request Forgery (SSRF)** - Unvalidated URLs, internal access

## Input Validation

### Always Validate

**User Input Sources:**
- Query parameters
- Request body
- Headers
- Uploaded files
- Cookie values
- Form data

**Validation Rules:**
- Whitelist acceptable values when possible
- Validate data type, length, format, range
- Reject invalid input (don't try to sanitize)
- Use strong typing (C# types, TypeScript interfaces)

**C# Example (Good):**
```csharp
[Authorize]
[HttpPost]
public async Task<IActionResult> UpdateTask([FromBody] TaskUpdateModel request)
{
    // Validation via model attributes
    if (!ModelState.IsValid)
        return BadRequest(ModelState);

    // Additional business validation
    if (request.TaskId <= 0)
        return Problem("Invalid task ID", statusCode: 400);

    // Proceed with validated input
}
```

**C# Example (Bad):**
```csharp
[HttpPost]
public async Task<IActionResult> UpdateTask([FromBody] dynamic request)
{
    // No validation! Anything could be in request
    var taskId = request.TaskId; // Could be null, negative, etc.
}
```

### File Upload Validation

**Check these for uploaded files:**
- File extension (whitelist acceptable types)
- MIME type (verify actual content, not just extension)
- File size (enforce limits)
- File content (scan for malware patterns if applicable)
- Storage location (prevent path traversal)

**Example:**
```csharp
public async Task<IActionResult> UploadFile(IFormFile file)
{
    var allowedExtensions = new[] { ".pdf", ".docx", ".txt" };
    var extension = Path.GetExtension(file.FileName).ToLowerInvariant();

    if (!allowedExtensions.Contains(extension))
        return Problem("File type not allowed", statusCode: 400);

    if (file.Length > 100_000_000) // 100MB
        return Problem("File too large", statusCode: 400);

    // Use safe file storage path
    var safeFileName = Path.GetRandomFileName();
    var filePath = Path.Combine(_uploadPath, safeFileName);

    using var stream = new FileStream(filePath, FileMode.Create);
    await file.CopyToAsync(stream);
}
```

## SQL Injection Prevention

See the Raw SQL rule in this dimension's PIP guideline excerpt. If a dynamic column/identifier is ever required (e.g. a sort column from user input), whitelist it against a known set rather than interpolating it directly into the query:

```csharp
private static readonly HashSet<string> AllowedColumns = new() { "TaskId", "Description", "DateCreated" };

public void GetTasks(string sortColumn)
{
    if (!AllowedColumns.Contains(sortColumn))
        throw new ArgumentException("Invalid column name");
}
```

## Cross-Site Scripting (XSS) Prevention

### Angular Automatic Escaping

Angular automatically escapes values in templates:

**Safe (automatically escaped):**
```html
<div>{{ userInput }}</div>
<div [title]="userInput"></div>
```

**Unsafe (bypasses sanitization):**
```typescript
// Avoid unless absolutely necessary and input is trusted
this.sanitizer.bypassSecurityTrustHtml(userInput);
```

### C# HTML Generation

When generating HTML in C#:

```csharp
// Use HtmlEncoder
var safeHtml = HtmlEncoder.Default.Encode(userInput);

// Or use a library like HtmlAgilityPack for complex scenarios
```

### JavaScript Injection

**Bad:**
```typescript
// Never use eval() with user input
eval(userCode); // Extremely dangerous!

// Never create script elements with user content
const script = document.createElement('script');
script.innerHTML = userInput; // Dangerous!
```

**Good:**
```typescript
// Use safe alternatives
const data = JSON.parse(userInput); // Safe for JSON data only

// For dynamic behavior, use data attributes and known functions
element.setAttribute('data-value', userInput);
```

## Authentication & Authorization

Authorization pattern (`[Authorize]`/policies) and franchise isolation are covered in this dimension's PIP guideline excerpt (`guidelines/security.md`) — verify both are present as part of this checklist.

## Sensitive Data Protection

### Secrets Management

**Never commit secrets:**
- Database connection strings
- API keys
- Passwords
- Private keys
- Certificates

**Good - Use configuration:**
```csharp
// appsettings.json or environment variables
var apiKey = _configuration["ExternalApi:ApiKey"];
```

**Bad - Hard-coded secrets:**
```csharp
// NEVER DO THIS!
const string ApiKey = "sk_live_abc123...";
```

### Logging Sensitive Data

**Don't log:**
- Passwords
- Credit card numbers
- Social Security numbers
- Authentication tokens
- Personal health information

**Good logging:**
```csharp
_logger.LogInformation("User {UserId} logged in successfully", userId);
```

**Bad logging:**
```csharp
_logger.LogInformation("User {Email} logged in with password {Password}",
    email, password); // Never log passwords!
```

### Error Messages

**Good - Generic errors to users:**
```csharp
return Problem("Authentication failed", statusCode: 401);
```

**Bad - Detailed errors expose information:**
```csharp
return Problem($"User {username} not found in database table 'users'",
    statusCode: 401);
// Reveals username validity, table names, DB structure
```

## Command Injection

### Process Execution

**Good - Avoid shell execution:**
```csharp
var process = new Process();
process.StartInfo.FileName = "convert"; // Direct executable
process.StartInfo.Arguments = $"-resize 800x600 \"{inputPath}\" \"{outputPath}\"";
process.StartInfo.UseShellExecute = false;
process.Start();
```

**Bad - Shell execution with user input:**
```csharp
// NEVER DO THIS!
Process.Start("cmd.exe", $"/c convert {userInput}");
```

### File Path Traversal

**Good - Validate paths:**
```csharp
public IActionResult DownloadFile(string fileName)
{
    // Validate filename doesn't contain path traversal
    if (fileName.Contains("..") || Path.IsPathRooted(fileName))
        return Problem("Invalid filename", statusCode: 400);

    var basePath = "/safe/upload/directory";
    var fullPath = Path.Combine(basePath, fileName);

    // Double-check resolved path is still within base directory
    if (!fullPath.StartsWith(basePath))
        return Problem("Invalid filename", statusCode: 400);

    return PhysicalFile(fullPath, "application/octet-stream");
}
```

**Bad - No validation:**
```csharp
public IActionResult DownloadFile(string fileName)
{
    // User could pass "../../etc/passwd"
    var path = Path.Combine("/uploads", fileName);
    return PhysicalFile(path, "application/octet-stream");
}
```

## Session Management

### Session Configuration

**Secure cookie settings:**
```csharp
services.AddSession(options =>
{
    options.Cookie.HttpOnly = true; // Prevent JavaScript access
    options.Cookie.SecurePolicy = CookieSecurePolicy.Always; // HTTPS only
    options.Cookie.SameSite = SameSiteMode.Strict; // CSRF protection
    options.IdleTimeout = TimeSpan.FromMinutes(30); // Reasonable timeout
});
```

### JWT Tokens

**Good practices:**
- Short expiration times (minutes to hours, not days)
- Use refresh tokens for long-lived sessions
- Store securely (httpOnly cookies, not localStorage)
- Validate signature and expiration on every request
- Include audience and issuer claims

## CSRF Protection

### State-Changing Operations

**Good - Use antiforgery tokens:**
```csharp
[HttpPost]
[ValidateAntiForgeryToken]
public async Task<IActionResult> UpdateSettings(SettingsModel settings)
{
    // Token validated by framework
}
```

**Frontend - Include CSRF token:**
```typescript
// Angular HttpClient automatically includes XSRF token
this.http.post('/api/settings', settings).subscribe();
```

### API Endpoints

For API endpoints used by non-browser clients:

```csharp
// Use bearer tokens instead of cookies
[Authorize(AuthenticationSchemes = JwtBearerDefaults.AuthenticationScheme)]
[HttpPost]
public async Task<IActionResult> ApiEndpoint()
{
    // CSRF not needed when using bearer tokens
}
```

## Security Headers

### Response Headers

**Configure security headers:**
```csharp
app.Use(async (context, next) =>
{
    context.Response.Headers.Add("X-Content-Type-Options", "nosniff");
    context.Response.Headers.Add("X-Frame-Options", "DENY");
    context.Response.Headers.Add("X-XSS-Protection", "1; mode=block");
    context.Response.Headers.Add("Referrer-Policy", "strict-origin-when-cross-origin");
    context.Response.Headers.Add("Content-Security-Policy",
        "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'");

    await next();
});
```

## Security Testing Checklist

When reviewing code, verify:

- [ ] All user input is validated
- [ ] SQL queries use parameters
- [ ] Authorization (`[Authorize]`/policy) checks are present on controllers
- [ ] No secrets in code
- [ ] Sensitive data not logged
- [ ] Error messages don't leak information
- [ ] File uploads are validated and stored safely
- [ ] Authentication tokens are secure
- [ ] CSRF protection on state-changing operations
- [ ] XSS prevention in HTML output
- [ ] Command injection prevention
- [ ] Path traversal prevention
- [ ] Session management is secure
- [ ] Security headers are configured
