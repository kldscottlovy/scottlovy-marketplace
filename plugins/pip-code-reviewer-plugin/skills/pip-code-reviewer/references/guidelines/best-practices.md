## PIP C# Best Practices Guidelines

### Type and Naming Conventions

- `var` preferred everywhere for local variables.
- PascalCase for public members/classes/methods; camelCase for locals/parameters; `_camelCase` (underscore prefix) for private instance fields.
- Allman-style braces, tab indentation, UTF-8 BOM.

### Async/Await Rules

**NEVER use `.Result` or `.Wait()` — they cause deadlocks in ASP.NET Core's async context.** Always `await`. All I/O must be async; return `Task`/`Task<T>`, never `void` except for event handlers.

### Error Handling

Return appropriate HTTP status codes from controllers. Do not leak internal exception messages to callers.

```csharp
// Good
catch (StateMachineValidationException)
{
	return Conflict("The task is not in a state that allows completing.");
}

// Bad — exposes internal state machine terminology to the caller
catch (StateMachineValidationException ex)
{
	return Conflict(ex.Message);
}
```
