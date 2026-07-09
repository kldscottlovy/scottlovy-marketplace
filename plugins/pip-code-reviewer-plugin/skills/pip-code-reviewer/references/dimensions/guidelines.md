---
key: guidelines
label: Project Guidelines
---
{{base_context}}

Review ONLY for Project Guidelines adherence:
- DTOs prefixed DTO_ and placed in PIP.WebApiModels
- IConcurrencyEntity DTOs must include RowVersion on request and response
- AutoMapper profiles for entity↔DTO mapping (never inline)
- No edits to auto-generated OpenAPI client (frontend/PipFrontend/ClientApp/src/app/core/api-resources/)
- EF entities in PIP.EF/Entities/PIP/
- Services depend on IXxxQueryProvider, not PIPContext

- Controllers depend on IXxxService, not IXxxQueryProvider or PIPContext

Return findings only for this dimension. Be specific with file paths and line numbers from the diff.
