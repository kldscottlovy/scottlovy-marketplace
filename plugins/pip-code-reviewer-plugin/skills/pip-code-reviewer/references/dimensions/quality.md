---
key: quality
label: Code Quality & Maintainability
---
{{base_context}}

{{quality}}

Review ONLY for Code Quality and Maintainability:
- Naming conventions (PascalCase public, camelCase private)
- Code readability and clarity
- Comment quality and XML documentation
- Cyclomatic complexity and method length
- Magic numbers and hard-coded values

#### Easy Fixes

- Boolean simplification (The expression 'A == true' can be simplified to 'A'.) or (The expression 'A == false' can be simplified to '!A'.) 

Return findings only for this dimension. Be specific with file paths and line numbers from the diff.
