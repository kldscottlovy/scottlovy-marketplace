# Testing Standards

Comprehensive testing best practices for the PIP Solution.

## Table of Contents

1. Test Organization
2. Testing Philosophy
3. AAA Pattern
4. Integration vs Unit Tests
5. Test Data Management
6. Common Testing Patterns
7. Playwright vs Selenium
8. API Testing
9. Testing Checklist

## Test Organization

### Test Project Structure

API Tests

```
tests\
├── PIP.ApiTesting.Utility\PIP.ApiTesting.Utility.csproj
├── PIP.ApiTests\PIP.ApiTests.csproj
├── PIP.ExternalApi.ApiServiceTests\PIP.ExternalApi.ApiServiceTests.csproj
├── PIP.ExternalApi.ApiTests\PIP.ExternalApi.ApiTests.csproj
└── PIP.ExternalApi.SmokeTests\PIP.ExternalApi.SmokeTests.csproj
```

Unit Tests

```
├── PIP.ExternalApi.Tests\PIP.ExternalApi.Tests.csproj
├── midtier\Pip.ExternalServices.Tests\Pip.ExternalServices.Tests.csproj
├── PIP.SharedApi.Tests\PIP.SharedApi.Tests.csproj
├── PIP.SharedBusinessLogic.Tests\PIP.SharedBusinessLogic.Tests.csproj
├── midtier\PipApi.Tests\PipApi.Tests.csproj
└── PipApi.TestsRestSharp\PipApi.TestsRestSharp.csproj
```

E2E Tests: `E2E.Tests\E2E.Tests.csproj` — E2E Playwright Tests: `E2ETestsPlaywright\E2ETestsPlaywright.csproj`

### Test Naming Conventions

Method naming pattern: `MethodName_ExpectedBehavior_Condition` (e.g. `GetTaskAsync_ReturnsNull_WhenNotFound`, `DeleteTaskAsync_ThrowsException_WhenUserLacksPermission`).

## Testing Philosophy

### No Distinction Between Unit and Integration Tests

**All tests in `Unit Tests` are simply "tests":**

- Don't create separate Unit/Integration folders
- Focus on testing behavior, not implementation details — assert on what a method returns or changes, not on which internal methods it called
- Use real dependencies when practical; mock only when necessary (external APIs, slow operations)

```csharp
// Good — tests behavior
var task = new PIP_Task { Description = "Test" };
await _service.CreateTaskAsync(task);
(await _service.GetTaskAsync(task.Id)).Description.Should().Be("Test");

// Bad — tests that an internal method was called, not the outcome
var mockQueryProvider = new Mock<ITaskQueryProvider>();
mockQueryProvider.Verify(r => r.AddAsync(It.IsAny<PIP_Task>()), Times.Once);
```

## AAA Pattern

Structure all tests as **Arrange-Act-Assert**:

```csharp
[Fact]
public async Task GetTaskAsync_ReturnsTask_WhenExists()
{
    // Arrange
    long taskId = 1;
    await _testDb.SeedTaskAsync(taskId, "Test Task");

    // Act
    PIP_Task? result = await _taskQueryProvider.GetTaskAsync(taskId);

    // Assert
    result.Should().NotBeNull();
    result!.Description.Should().Be("Test Task");
}
```

For complex, multi-step scenarios (e.g. a task's create → update → complete lifecycle), multiple Act-Assert cycles in one test are acceptable — just label each one (`// Act 1`, `// Assert 1`, etc.).

## Integration vs Unit Tests

**Prefer integration tests** (real database, real services) for database operations, multi-component workflows, API endpoints, and external service interactions — e.g. a job handler that processes invoices end-to-end and asserts the resulting `InvoiceStatusEnum`.

**Prefer unit tests** for pure logic without dependencies: algorithms, validation logic, utility functions. `[Theory]`/`[InlineData]` is the standard way to cover multiple cases of a pure function without repeating the test body.

## Test Data Management

- **Always clean up test data.** Track created IDs (tasks, work requests, etc.) in a list and delete them in `DisposeAsync` (via `IAsyncLifetime`), in reverse order of creation.
- **Use fixtures (`IClassFixture<T>`) for data shared across multiple tests** in a class — e.g. a seeded test work request/user — rather than reseeding per test.
- **Each test must be independent** — create the specific data it needs rather than assuming a fixed ID exists (`DeleteTaskAsync(1)` is fragile; creating a task first and deleting *that* one isn't).

```csharp
public class TaskTests : IAsyncLifetime
{
    private readonly List<long> _createdTaskIds = new();

    [Fact]
    public async Task CreateTask_AddsToWorkRequest()
    {
        var task = new PIP_Task { Description = "Test", WorkRequestId = _fixture.TestWorkRequestId };
        await _service.CreateTaskAsync(task);
        _createdTaskIds.Add(task.Id); // Track for cleanup

        (await _service.GetTaskAsync(task.Id)).Should().NotBeNull();
    }

    public async Task DisposeAsync()
    {
        foreach (long id in _createdTaskIds)
            await _taskQueryProvider.DeleteTaskAsync(id);
    }
}
```

## Common Testing Patterns

**FluentAssertions** is used for all assertions — collections (`.Should().HaveCount(5)`, `.AllSatisfy(...)`), nulls (`.Should().NotBeNull()`), numerics/strings (`.Should().BeGreaterThan(0)`, `.Should().Contain(...)`), exceptions (`await act.Should().ThrowAsync<T>().WithMessage("*text*")`), and object comparisons (`.Should().BeEquivalentTo(expected, o => o.Excluding(x => x.Id))`).

```csharp
[Fact]
public async Task DeleteTask_ThrowsException_WhenNotFound()
{
    Func<Task> act = async () => await _service.DeleteTaskAsync(999999);
    await act.Should().ThrowAsync<TaskNotFoundException>().WithMessage("*999999*");
}
```

Never use `.Result` or `.Wait()` in tests — same deadlock risk as production code; always `await`.

## Playwright vs Selenium

**Prefer Playwright for new E2E tests** — faster, better async support, auto-wait for elements, better debugging. Migrate existing Selenium tests to Playwright when touching that area, fixing flakiness, or doing a larger test refactor; otherwise leave existing Selenium tests (`E2ETestBase`) as-is.

```csharp
public class TaskListTests : PageTest
{
    [Test]
    public async Task TaskList_DisplaysTasks()
    {
        await Page.GotoAsync("/tasks");
        var taskRows = await Page.Locator(".task-row").AllAsync();
        taskRows.Should().HaveCountGreaterThan(0);
    }
}
```

## API Testing

API tests should verify both success and error cases, and clean up any created resources in `DisposeAsync`:

```csharp
public class TaskApiTests : ApiTestBase
{
    private readonly List<long> _createdTaskIds = new();

    [Fact]
    public async Task CreateTask_ReturnsCreated()
    {
        var response = await _client.CreateTaskAsync(new DTO_TaskCreateRequest { Description = "Test Task" });
        response.Id.Should().BeGreaterThan(0);
        _createdTaskIds.Add(response.Id); // Track for cleanup
    }

    [Fact]
    public async Task DeleteTask_Returns404_WhenNotFound()
    {
        Func<Task> act = async () => await _client.DeleteTaskAsync(999999);
        await act.Should().ThrowAsync<ApiException>().Where(e => e.StatusCode == 404);
    }

    public override async Task DisposeAsync()
    {
        foreach (long id in _createdTaskIds)
            try { await _client.DeleteTaskAsync(id); } catch { /* ignore cleanup failures */ }
        await base.DisposeAsync();
    }
}
```

## Testing Checklist

When reviewing tests, verify:

- [ ] AAA pattern followed (or multiple Act-Assert cycles for complex scenarios)
- [ ] Test names follow convention: `MethodName_ExpectedBehavior_Condition`
- [ ] Tests use real dependencies (e.g. `(localdb)\mssqllocaldb`) not in-memory providers, and aren't over-mocked
- [ ] FluentAssertions used for assertions
- [ ] Async/await used properly (no .Result or .Wait())
- [ ] Test data is created and cleaned up; no shared mutable state across tests
- [ ] Tests are independent (don't rely on execution order or hardcoded IDs)
- [ ] No `Task.Delay`/sleep-based waits — poll with a timeout instead
- [ ] Playwright used for new E2E tests (not Selenium)
- [ ] API tests verify both success and error cases
- [ ] Exception tests use `Should().ThrowAsync<>()`
- [ ] Tests focus on behavior, not implementation details
