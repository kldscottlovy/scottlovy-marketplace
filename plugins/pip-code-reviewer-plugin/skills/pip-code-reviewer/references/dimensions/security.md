---
key: security
label: Security
---
{{base_context}}

{{security}}

Security checklist:
{{security-checklist}}

**Core Instructions**
- Report only genuine security issues. Do not nitpick style or non-security concerns.
- When multiple issues exist, prioritize by exploitability and real-world impact.
- If you find a critical issue (exposed secrets, auth bypass, franchise data leak), flag it immediately at the top of your response — don't bury it in a long list.
- Organize findings by severity: **Critical** → **High** → **Medium** → **Low**.

Review ONLY for Security:
- Secrets & environment variables — hardcoded API keys, tokens, or credentials
- Input validation
- Authentication/authorization checks
- SQL injection prevention
- XSS prevention
- Sensitive data handling
- Error handling without information leakage
- Security headers and deployment/environment configuration, where applicable
- Franchise user queries MUST filter by user.IsFranchiseUser + user.AccessRestrictionIds (omitting = silent data leak)

Return findings only for this dimension. Be specific with file paths and line numbers from the diff.
