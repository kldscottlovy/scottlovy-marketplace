---
key: duplication
label: Duplication & Consolidation
---
{{base_context}}

{{duplication}}

You have access to the full current content of every changed file, plus their state on the base branch before this branch diverged:

{{full_file_contents}}

Review ONLY for Code Duplication and Consolidation opportunities introduced by this branch compared to the base branch it will merge into:

**Duplication to detect:**
- Identical or near-identical code blocks that appear in more than one place — in the new code, or between new code and existing code in the base branch
- Copy-pasted logic with minor variable name changes (same structural pattern, different identifiers)
- Repeated LINQ query patterns that could be extracted into a shared QueryProvider extension or helper
- Multiple methods/classes performing the same transformation, mapping, or validation with slight differences
- Parallel structures in handlers or services that differ only by entity type — a sign that a generic base class or shared helper is warranted

**Consolidation to suggest:**
- Where the new code duplicates logic already present elsewhere in the codebase, point to the existing implementation and suggest calling it instead
- Where two or more new methods share structure, suggest a private helper, extension method, base class, or shared service
- Where scattered filtering, sorting, or pagination logic could be centralized into a QueryProvider method
- Where AutoMapper profile logic is duplicated across profiles
- Where exception handling, logging, or validation patterns are repeated inline instead of being centralized

**Architectural improvements implied by duplication:**
- If the same concern appears in multiple layers (controller + service + handler), flag the layer violation and suggest where it belongs
- If duplication spans multiple domain areas, suggest a shared utility in PIP.SharedBusinessLogic or PIP.Common
- Rank refactoring suggestions by impact: high (eliminates a bug vector or data-consistency risk), medium (meaningfully reduces maintenance surface), low (cosmetic improvement)

For each finding, provide:
- The specific files and line numbers where duplication exists
- A concrete refactoring approach (method signature, class name, target project/namespace)
- Estimated lines eliminated and maintenance risk reduced

Report critical duplication only as Important or Suggestions — duplication is never Critical unless it also introduces a correctness or security risk (flag that in the Security or Architecture dimension instead).

Return findings only for this dimension. Be specific with file paths and line numbers.
