---
key: architecture
label: Architecture & Patterns
---
{{base_context}}

{{architecture}}

Review ONLY for Architecture & Patterns:
- QueryProvider pattern (services must use IXxxQueryProvider, never PIPContext directly)
- Appropriate layer separation
- Dependency injection usage (Autofac conventions)
- Database access patterns (no global soft-delete filter — always filter IsDeleted = false manually)
- Domain event placement (MediatR, post-commit visibility)
- State machine usage

Return findings only for this dimension. Be specific with file paths and line numbers from the diff.
