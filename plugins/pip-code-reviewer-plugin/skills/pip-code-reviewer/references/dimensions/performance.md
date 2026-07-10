---
key: performance
label: Performance
---
{{base_context}}

Review ONLY for Performance:
- Database query efficiency
- N+1 query problems
- Unnecessary loops or iterations
- Memory management
- Async/await usage
- Missing indexes implied by new queries
- Database Race Conditions (check-then-act) dealing with 
  - Entity Framework Async commands (AnyAsync combined with an Add and SaveChangesAsync)


Return findings only for this dimension. Be specific with file paths and line numbers from the diff.
