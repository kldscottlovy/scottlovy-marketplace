## PIP Architecture Guidelines

### Where Code Belongs

- **Controllers** — routing, auth attributes, DTO mapping via AutoMapper, delegate to services
- **Services** — all business logic; depends on `IXxxQueryProvider` via DI, never communicates with `PIPContext` directly
- **QueryProviders** — all EF Core queries; take `PIPContext` via DI
- **EF Entities** — in `PIP.EF/Entities/PIP/`

### QueryProvider Pattern

Every domain area has `IXxxQueryProvider` (interface, in `PIP.SharedBusinessLogic`), `XxxQueryProvider` (implementation, takes `PIPContext` via DI), and `XxxService` (business logic, depends on `IXxxQueryProvider`, never `PIPContext`).

```csharp
// Good — service depends on interface, never PIPContext
public class TaskCompleteService
{
	private readonly ITaskQueryProvider _taskQueryProvider;
	public TaskCompleteService(ITaskQueryProvider taskQueryProvider) { _taskQueryProvider = taskQueryProvider; }
}

// Bad — service takes PIPContext directly
public class TaskCompleteService
{
	private readonly PIPContext _context; // Never do this in a service
}
```

### No Global Soft-Delete Filter

PIP has **no global soft-delete filter** on `PIPContext`. If an entity has an `IsDeleted` field, every query against it must filter `!t.IsDeleted` manually — there's no automatic enforcement. If the entity has no `IsDeleted` field, this rule doesn't apply.

### Dependency Injection (Autofac)

PIP uses **Autofac**. All types in `PIP.SharedBusinessLogic` are auto-registered by convention (`AsImplementedInterfaces`, `InstancePerDependency`) — no manual registration needed when adding a new `IXxxQueryProvider`/`XxxQueryProvider` or `IXxxService`/`XxxService` pair.

### Domain Events (MediatR)

Events live under `midtier/PipApi/DomainEvents/`. `PIPContext` publishes `PublishBeforeSaveChangesAsync()` (before commit) and `PublishAfterSaveChangesAsync()` (after commit — the only events visible externally). A handler firing on `BeforeSaveChanges` that calls its own `SaveChangesAsync` can produce orphaned records if the outer save later fails — that logic belongs in a post-commit handler instead.

### State Machine (Stateless)

PIP uses the **Stateless** library. `TaskStateMachine` lives in `PIP.SharedBusinessLogic/StateMachine/`, with `ConfigureXxx` transition classes under `StateMachine/Configuration/`. Task state transitions must always go through the state machine (`await _taskStateMachine.FireAsync(TaskTrigger.Complete, task)`) — never mutate `task.Status` directly, which bypasses validators and domain events.
