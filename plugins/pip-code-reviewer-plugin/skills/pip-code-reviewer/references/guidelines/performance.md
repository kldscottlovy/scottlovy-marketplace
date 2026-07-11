## PIP Performance Guidelines

All database access goes through the QueryProvider pattern (EF Core 9.0 on SQL Server). Use `ProjectTo<T>` (AutoMapper) on EF Core queries to push projection to SQL rather than materializing full entities first:

```csharp
// Good — projects at the database level
var results = await _context.Tasks.Where(t => !t.IsDeleted)
	.ProjectTo<DTO_Task>(_mapper.ConfigurationProvider).ToListAsync();
```

All I/O must be async — synchronous blocking calls (or `.Result`/`.Wait()` on async calls) block a thread-pool thread and hurt throughput under load, in addition to the deadlock risk.
