# C# Backend Development Guidelines

Guidelines for C# backend development in PIP (Process Intelligence Platform) — an enterprise invoice/matter processing application for legal discovery.

## Table of Contents

1. Project Structure and Code Location
2. Type Usage and Conventions
3. Data Access Patterns (EF Core + QueryProvider)
4. Async/Await Rules
5. Authentication, Authorization, and Franchise Filtering
6. DTOs and Models
7. AutoMapper
8. Dependency Injection (Autofac)
9. Domain Events (MediatR)
10. State Machine (Stateless)
11. EF Entity Interfaces
12. Error Handling
13. Common Anti-Patterns

---

## Project Structure and Code Location

```
PIP/
├── midtier/PipApi/               → Main REST API (controllers, state machine, domain events)
├── PIP.InternalApi/              → Internal-only admin endpoints
├── midtier/PIP.ExternalApi/      → Third-party integration endpoints
├── PIP.SharedBusinessLogic/      → All domain services + QueryProviders (business logic layer)
├── PIP.EF/Entities/PIP/          → Core EF entities: Task, WorkRequest, Project, Invoice, User
├── PIP.EF/PIPContext.cs           → DbContext (audit, domain events, concurrency, soft-delete hooks)
├── PIP.WebApiModels/              → Shared DTOs across APIs (all prefixed DTO_)
├── PIP.Common/                    → Shared enums + utility types
├── PIP.AzureFunctions/            → Timer-triggered background sync jobs
├── PIP.EmailApp/                  → Email queue processing worker
├── PIP.WorkerServiceApp/          → Windows Service / Azure WebJob runner
└── frontend/PipFrontend/ClientApp/src/app/
    ├── core/api-resources/        → AUTO-GENERATED — NEVER edit manually
    └── shared/                    → 50+ reusable components
```

### Where Code Belongs

- **Controllers** — routing, auth attributes, DTO mapping via AutoMapper, delegate to services
- **Services** (`PIP.SharedBusinessLogic`) — all business logic; depend on `IXxxQueryProvider`, never `PIPContext` directly
- **QueryProviders** (`PIP.SharedBusinessLogic`) — all EF Core queries; take `PIPContext` via DI
- **DTOs** — in `PIP.WebApiModels`, prefixed `DTO_`
- **EF Entities** — in `PIP.EF/Entities/PIP/`
- **Migrations** — in `midtier/PipApi/Migrations/` (compile only inside PipApi)

---

## Type Usage and Conventions

### Use `var` Everywhere

PIP prefers `var` for all local variable declarations:

```csharp
// Good
var task = await _taskQueryProvider.GetTaskAsync(taskId);
var results = await _context.Tasks.Where(t => !t.IsDeleted).ToListAsync();
```

```csharp
// Bad — explicit types are unnecessarily verbose in PIP
PIP_Task task = await _taskQueryProvider.GetTaskAsync(taskId);
List<PIP_Task> results = await _context.Tasks.Where(t => !t.IsDeleted).ToListAsync();
```

### Naming Conventions

- **PascalCase** — public members, constants, classes, methods
- **camelCase** — local variables and method parameters
- **`_camelCase`** — private instance fields (underscore prefix required)
- **`DTO_`** prefix — all DTO classes (e.g. `DTO_InvoiceBatch`, `DTO_TaskComplete`)

### Braces and Formatting

- Allman-style braces (opening brace on its own line)
- Indentation: **tabs** (not spaces — ESLint overrides `.editorconfig` in frontend too)
- UTF-8 BOM on C# files

```csharp
// Good — Allman braces, tabs
public async Task<DTO_Task> GetTaskAsync(long taskId)
{
	var task = await _taskQueryProvider.GetTaskAsync(taskId);
	if (task == null)
	{
		return null;
	}
	return _mapper.Map<DTO_Task>(task);
}
```

---

## Data Access Patterns (EF Core + QueryProvider)

PIP uses **EF Core 9.0** on **SQL Server**. All database access goes through the QueryProvider pattern.

### QueryProvider Pattern

Every domain area has:
- `IXxxQueryProvider` — interface in `PIP.SharedBusinessLogic`
- `XxxQueryProvider` — implementation that takes `PIPContext` via DI
- `XxxService` — business logic that depends on `IXxxQueryProvider`, never `PIPContext`

```csharp
// Good — service depends on interface, never PIPContext
public class TaskCompleteService
{
	private readonly ITaskQueryProvider _taskQueryProvider;
	private readonly ITaskBillingQueryProvider _taskBillingQueryProvider;

	public TaskCompleteService(
		ITaskQueryProvider taskQueryProvider,
		ITaskBillingQueryProvider taskBillingQueryProvider)
	{
		_taskQueryProvider = taskQueryProvider;
		_taskBillingQueryProvider = taskBillingQueryProvider;
	}
}
```

```csharp
// Bad — service takes PIPContext directly
public class TaskCompleteService
{
	private readonly PIPContext _context; // Never do this in a service
}
```

### No Global Soft-Delete Filter

PIP has **no global soft-delete filter** on `PIPContext`. 

Before reporting a `soft-delete` error, check the associated entity to guarantee that it has a `IsDeleted` field.  I there is no `IsDeleted` field then do not report a review issue.

If a `IsDeleted` field exists, you must always filter manually:

```csharp
// Good — always filter IsDeleted = false explicitly
var tasks = await _context.Tasks
	.Where(t => !t.IsDeleted && t.WorkRequestId == workRequestId)
	.ToListAsync();
```

```csharp
// Bad — omitting IsDeleted filter returns deleted records silently
var tasks = await _context.Tasks
	.Where(t => t.WorkRequestId == workRequestId)
	.ToListAsync();
```

### EF Core Raw SQL

When using raw SQL, always use `ExecuteSqlInterpolatedAsync` — it auto-parameterizes and prevents SQL injection:

```csharp
// Good — ExecuteSqlInterpolatedAsync auto-parameterizes
await _context.Database.ExecuteSqlInterpolatedAsync(
	$"INSERT INTO TaskAudit (TaskId, Action) VALUES ({taskId}, {action})");
```

```csharp
// Bad — ExecuteSqlRawAsync with string interpolation is SQL injection
await _context.Database.ExecuteSqlRawAsync(
	$"INSERT INTO TaskAudit (TaskId, Action) VALUES ({taskId}, {action})");
```

---

## Async/Await Rules

**NEVER use `.Result` or `.Wait()` — they cause deadlocks in ASP.NET Core's async context.**

```csharp
// Good — always await
var task = await _taskQueryProvider.GetTaskAsync(taskId);
```

```csharp
// Bad — DEADLOCK RISK
var task = _taskQueryProvider.GetTaskAsync(taskId).Result;
_taskQueryProvider.GetTaskAsync(taskId).Wait();
```

All I/O operations must be async. Return `Task` or `Task<T>` — never `void` except for event handlers.

---

## Authentication, Authorization, and Franchise Filtering

### Franchise User Queries

**Franchise user queries MUST filter by both `user.IsFranchiseUser` and `user.AccessRestrictionIds`. Omitting either is a silent data leak.**

```csharp
// Good — franchise isolation enforced
public async Task<List<DTO_WorkRequest>> GetWorkRequestsAsync(UserContext user)
{
	var query = _context.WorkRequests.Where(wr => !wr.IsDeleted);

	if (user.IsFranchiseUser)
	{
		query = query.Where(wr => user.AccessRestrictionIds.Contains(wr.ClientId));
	}

	return await query.ProjectTo<DTO_WorkRequest>(_mapper.ConfigurationProvider).ToListAsync();
}
```

```csharp
// Bad — franchise users can see all records (data leak)
public async Task<List<DTO_WorkRequest>> GetWorkRequestsAsync()
{
	return await _context.WorkRequests
		.Where(wr => !wr.IsDeleted)
		.ProjectTo<DTO_WorkRequest>(_mapper.ConfigurationProvider)
		.ToListAsync();
}
```

### Authorization Attributes

Authorization is enforced via policy attributes on controllers. Services assume the caller has already been authorized.

---

## DTOs and Models

All DTOs are:
- Prefixed with `DTO_` (e.g. `DTO_Task`, `DTO_InvoiceBatch`, `DTO_TaskCompleteRequest`)
- Placed in `PIP.WebApiModels`
- Mapped to/from entities exclusively via AutoMapper profiles — **never inline**

### IConcurrencyEntity DTOs

For any DTO mapping to an entity that implements `IConcurrencyEntity`, **both request and response DTOs must include `RowVersion`**. A null `RowVersion` will cause a concurrency failure.

```csharp
// Good — RowVersion on both request and response
public class DTO_TaskUpdateRequest
{
	public long TaskId { get; set; }
	public string Description { get; set; }
	public byte[] RowVersion { get; set; } // Required — concurrency token
}

public class DTO_TaskResponse
{
	public long TaskId { get; set; }
	public string Description { get; set; }
	public byte[] RowVersion { get; set; } // Required — client needs this for next update
}
```

```csharp
// Bad — missing RowVersion will cause EF concurrency failure
public class DTO_TaskUpdateRequest
{
	public long TaskId { get; set; }
	public string Description { get; set; }
	// Missing RowVersion!
}
```

- Classes that are models should always leave the API at some controller.
- Models should always be named `xxxxxxxModel.cs`
- It is possible to have a query provider method return a model if the fields do not change all the way up to the controller output.
- Controllers must always output models or nothing.
- Enums get put in a folder named enums and get named `xxxxxxxxEnum.cs`

### Auto-Generated OpenAPI Client

**`frontend/PipFrontend/ClientApp/src/app/core/api-resources/` is auto-generated from OpenAPI. Never edit it manually — changes will be overwritten.**

---

## AutoMapper

All entity↔DTO mapping lives in AutoMapper profiles. Each domain area has an `Automapper/` subfolder with a `*MapperProfile`.

```csharp
// Good — mapping in profile
public class TaskMapperProfile : Profile
{
	public TaskMapperProfile()
	{
		CreateMap<PIP_Task, DTO_Task>();
		CreateMap<DTO_TaskCreateRequest, PIP_Task>();
	}
}
```

```csharp
// Bad — inline mapping in service or controller
var dto = new DTO_Task
{
	TaskId = task.Id,
	Description = task.Description,
	// ... manual mapping
};
```

Use `ProjectTo<T>` for EF Core queries to push projection to SQL:

```csharp
// Good — projects at the database level
var results = await _context.Tasks
	.Where(t => !t.IsDeleted)
	.ProjectTo<DTO_Task>(_mapper.ConfigurationProvider)
	.ToListAsync();
```

---

## Dependency Injection (Autofac)

PIP uses **Autofac**. All types in `PIP.SharedBusinessLogic` are auto-registered by convention in `SharedBusinessLogicModule`:
- `AsImplementedInterfaces`
- `InstancePerDependency`

**No manual registration is needed** when adding a new `IXxxQueryProvider`/`XxxQueryProvider` pair or `IXxxService`/`XxxService` pair. Adding the types is sufficient.

```csharp
// Good — implementing the interface is all that's needed; Autofac picks it up automatically
public interface ITaskBillingQueryProvider { ... }
public class TaskBillingQueryProvider : ITaskBillingQueryProvider { ... }
```

---

## Domain Events (MediatR)

Domain events are implemented with MediatR. Events live under `midtier/PipApi/DomainEvents/`.

`PIPContext` publishes two phases:
- `PublishBeforeSaveChangesAsync()` — fires **before** the database transaction commits
- `PublishAfterSaveChangesAsync()` — fires **after** commit; these are the only events visible externally

**Handlers that write to the database must use `SaveChangesAsync` carefully.** A handler firing `BeforeSaveChanges` that calls its own `SaveChangesAsync` can produce orphaned records if the outer save subsequently fails.

```csharp
// Good — post-commit handler; outer transaction already succeeded
public class TaskCompletedEventHandler : INotificationHandler<TaskCompletedEvent>
{
	public async Task Handle(TaskCompletedEvent notification, CancellationToken ct)
	{
		// Safe to write — outer transaction already committed
		_context.TaskAuditLog.Add(new TaskAuditLog { TaskId = notification.TaskId });
		await _context.SaveChangesAsync(ct);
	}
}
```

---

## State Machine (Stateless)

PIP uses the **Stateless** NuGet library. `TaskStateMachine` lives in `midtier/PipApi/BusinessServices/StateMachine/`. `ConfigureXxx` classes define state→trigger→state transitions. `IStateValidator` checks preconditions before transitions fire.

When completing or transitioning a task, always go through the state machine — never mutate `task.Status` directly.

```csharp
// Good — state transition via state machine
await _taskStateMachine.FireAsync(TaskTrigger.Complete, task);
```

```csharp
// Bad — direct status mutation bypasses validators and domain events
task.Status = TaskStatus.Done;
await _context.SaveChangesAsync();
```

---

## EF Entity Interfaces

| Interface | Purpose |
|---|---|
| `IConcurrencyEntity` | Adds `RowVersion`; enables optimistic concurrency — always include in DTOs |
| `ISoftDeleteEntity` | Adds `IsDeleted` — never filtered globally, always filter manually |
| `ILastUpdateEntity` | Auto-stamps `LastUpdatedAt` / `LastUpdatedBy` via `PIPContext` hooks |
| `IAuditEntity` | Triggers creation of an audit row on save |

---

## Error Handling

Return appropriate HTTP status codes from controllers. Do not leak internal exception messages to callers.

```csharp
// Good — controlled error response
var task = await _taskQueryProvider.GetTaskAsync(taskId);
if (task == null)
	return NotFound();

try
{
	await _taskStateMachine.FireAsync(TaskTrigger.Complete, task);
}
catch (StateMachineValidationException)
{
	return Conflict("The task is not in a state that allows completing.");
}
```

```csharp
// Bad — leaks internal exception message to the caller
catch (StateMachineValidationException ex)
{
	return Conflict(ex.Message); // Exposes internal state machine terminology
}
```

---

## Common Anti-Patterns

### `.Result` / `.Wait()` on async calls
Causes deadlocks in ASP.NET Core. Always `await`.

### Calling `PIPContext` from a Service
Services must use `IXxxQueryProvider`. Direct `PIPContext` access from a service bypasses the testable query abstraction and violates the QueryProvider pattern.

### Omitting `IsDeleted = false`
There is no global soft-delete filter. Every query against a soft-deletable entity must explicitly filter `!t.IsDeleted`.

### Inline Entity↔DTO Mapping
All mapping belongs in AutoMapper profiles. Inline mapping in controllers or services bypasses profile reuse and is untestable in isolation.

### Missing `RowVersion` on Concurrency Entities
Any DTO for an entity implementing `IConcurrencyEntity` must include `RowVersion` on both request and response. Null `RowVersion` causes a concurrency exception.

### Omitting Franchise Filtering
Any query that returns data to a user must check `user.IsFranchiseUser` and apply `user.AccessRestrictionIds`. Omitting this is a silent data leak.

### Editing Auto-Generated API Client
`frontend/PipFrontend/ClientApp/src/app/core/api-resources/` is generated from OpenAPI on every build. Manual edits will be lost.

### `ExecuteSqlRawAsync` with String Interpolation
Always use `ExecuteSqlInterpolatedAsync` for raw SQL — it auto-parameterizes, preventing SQL injection.

---

## Code Review Checklist

- [ ] `var` used for local variables
- [ ] Private fields use `_camelCase` prefix
- [ ] DTOs prefixed `DTO_` and placed in `PIP.WebApiModels`
- [ ] No `.Result` or `.Wait()` — all async properly awaited
- [ ] `IsDeleted = false` filter present on every soft-deletable query
- [ ] Franchise user queries filter by `IsFranchiseUser` + `AccessRestrictionIds`
- [ ] `IConcurrencyEntity` DTOs include `RowVersion` on request and response
- [ ] All entity↔DTO mapping in AutoMapper profiles, not inline
- [ ] Services depend on `IXxxQueryProvider`, never `PIPContext`
- [ ] EF entities in `PIP.EF/Entities/PIP/`
- [ ] No manual edits to auto-generated OpenAPI client
- [ ] Raw SQL uses `ExecuteSqlInterpolatedAsync`, not `ExecuteSqlRawAsync` with interpolation
- [ ] State transitions go through the state machine, not direct `task.Status` mutation
- [ ] Domain event handlers that write data fire post-commit, not pre-commit
