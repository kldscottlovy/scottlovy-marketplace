## PIP Security Guidelines

### Franchise Filtering

**Franchise user queries MUST filter by both `user.IsFranchiseUser` and `user.AccessRestrictionIds`. Omitting either is a silent data leak.**

```csharp
// Good — franchise isolation enforced
public async Task<List<DTO_WorkRequest>> GetWorkRequestsAsync(UserContext user)
{
	var query = _context.WorkRequests.Where(wr => !wr.IsDeleted);
	if (user.IsFranchiseUser)
		query = query.Where(wr => user.AccessRestrictionIds.Contains(wr.ClientId));
	return await query.ProjectTo<DTO_WorkRequest>(_mapper.ConfigurationProvider).ToListAsync();
}

// Bad — franchise users can see all records (data leak)
public async Task<List<DTO_WorkRequest>> GetWorkRequestsAsync()
{
	return await _context.WorkRequests.Where(wr => !wr.IsDeleted)
		.ProjectTo<DTO_WorkRequest>(_mapper.ConfigurationProvider).ToListAsync();
}
```

### Authorization

Enforced via `[Authorize]` attributes with named policies (registered in `ServiceCollectionExtension.cs`, e.g. `Policies.RequireAuthenticatedUser`) at the controller level. Services assume the caller is already authorized.

### Raw SQL

All data access goes through EF Core (LINQ auto-parameterizes). If raw SQL is unavoidable, always use `ExecuteSqlInterpolatedAsync` (auto-parameterizes) — never `ExecuteSqlRawAsync` with string interpolation (SQL injection).

### Error Handling

Don't leak internal exception messages to callers (e.g. `return Conflict(ex.Message)` exposes internal terminology) — return a controlled, generic message instead.
