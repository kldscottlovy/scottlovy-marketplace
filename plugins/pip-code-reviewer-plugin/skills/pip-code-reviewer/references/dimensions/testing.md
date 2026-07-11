---
key: testing
label: Testing
---
{{base_context}}

{{testing}}

Testing standards:
{{testing-standards}}

Review ONLY for Testing:
- Adequate test coverage for changed code
- Test quality and clarity
- API Test vs Integration Test vs unit Test appropriateness
- Test data cleanup
- Missing edge case coverage
- Any regression required testing
- Fields set via object initializers on entities passed to a mocked `Add`/`Insert` (e.g. `IConcurrencyEntity.RowVersion`, non-nullable `DateTime` columns like `AuthorizedDateTime`, required FK ids) that no test asserts on — since the query provider is mocked, a dropped field won't fail until it hits a real non-nullable DB column

Return findings only for this dimension. Be specific with file paths and line numbers from the diff.
