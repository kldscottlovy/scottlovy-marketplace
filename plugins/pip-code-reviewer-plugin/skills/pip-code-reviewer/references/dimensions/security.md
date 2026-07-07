---
key: security
label: Security
---
{{base_context}}

Security checklist:
{{security-checklist}}

Review ONLY for Security:
- Input validation
- Authentication/authorization checks
- SQL injection prevention
- XSS prevention
- Sensitive data handling
- Error handling without information leakage
- Franchise user queries MUST filter by user.IsFranchiseUser + user.AccessRestrictionIds (omitting = silent data leak)

Return findings only for this dimension. Be specific with file paths and line numbers from the diff.
