# Testing Standards

Comprehensive testing best practices for the Nebula eDiscovery platform.

## Table of Contents

1. Test Organization
2. Testing Philosophy
3. AAA Pattern
4. Integration vs Unit Tests
5. Test Data Management
6. Common Testing Patterns
7. Playwright vs Selenium
8. API Testing

## Test Organization

### Test Project Structure

Tests are organized alongside the code they test:

```
src/Backend/csharp/
├── Nebula.Modules.Platform/
└── Nebula.Modules.Platform.Tests/

test/
├── APITests/              # API integration tests
├── E2E/NebulaE2ETest/    # Selenium E2E tests (legacy)
├── PwE2ETests/           # Playwright E2E tests (preferred)
└── DataSeeder/           # Test data setup
```

### Test Naming Conventions

**Method naming pattern:**
```
MethodName_ExpectedBehavior_Condition
```

**Examples:**
```csharp
[Fact]
public async Task GetDocumentAsync_ReturnsDocument_WhenExists()

[Fact]
public async Task GetDocumentAsync_ReturnsNull_WhenNotFound()

[Fact]
public async Task DeleteDocumentAsync_ThrowsException_WhenUserLacksPermission()
```

## Testing Philosophy

### No Distinction Between Unit and Integration Tests

**In Nebula, all tests in `*.Tests` projects are simply "tests":**
- Don't create separate Unit/Integration folders
- Focus on testing behavior, not implementation details
- Use real dependencies when practical
- Mock only when necessary (external APIs, slow operations)

### Use Docker Compose for External Dependencies

**No in-memory providers. Use real services:**

```csharp
public class DocumentRepositoryTests : IAsyncLifetime
{
    private readonly TestDatabase _testDb;
    private readonly DocumentRepository _repository;

    public DocumentRepositoryTests()
    {
        // Uses Docker PostgreSQL instance
        _testDb = new TestDatabase("test_documents");
        _repository = new DocumentRepository(_testDb.DataSource);
    }

    public async Task InitializeAsync()
    {
        await _testDb.CreateAsync();
        await _testDb.SeedDataAsync();
    }

    public async Task DisposeAsync()
    {
        await _testDb.DropAsync();
    }
}
```

### Test Behavior, Not Implementation

**Good - Tests behavior:**
```csharp
[Fact]
public async Task CreateDocument_AddsDocumentToRepository()
{
    // Arrange
    var document = new Document { Title = "Test" };

    // Act
    await _service.CreateDocumentAsync(document);

    // Assert
    var retrieved = await _service.GetDocumentAsync(document.Id);
    retrieved.Should().NotBeNull();
    retrieved.Title.Should().Be("Test");
}
```

**Bad - Tests implementation details:**
```csharp
[Fact]
public async Task CreateDocument_CallsRepositoryAdd()
{
    // Don't test that internal methods are called
    // Test the observable behavior instead
    var mockRepo = new Mock<IDocumentRepository>();
    mockRepo.Setup(r => r.AddAsync(It.IsAny<Document>()));

    // This tests implementation, not behavior
    mockRepo.Verify(r => r.AddAsync(It.IsAny<Document>()), Times.Once);
}
```

## AAA Pattern

### Arrange-Act-Assert

**Structure all tests with AAA pattern:**

```csharp
[Fact]
public async Task GetDocumentAsync_ReturnsDocument_WhenExists()
{
    // Arrange - Set up test data and dependencies
    int documentId = 1;
    var expectedTitle = "Test Document";
    await _testDb.SeedDocumentAsync(documentId, expectedTitle);

    // Act - Perform the operation being tested
    Document? result = await _repository.GetDocumentAsync(documentId);

    // Assert - Verify the outcome
    result.Should().NotBeNull();
    result!.Id.Should().Be(documentId);
    result.Title.Should().Be(expectedTitle);
}
```

### Multiple Act-Assert Cycles

**For complex scenarios, multiple Act-Assert cycles are acceptable:**

```csharp
[Fact]
public async Task DocumentLifecycle_CreatesUpdatesAndDeletes()
{
    // Arrange
    var document = new Document { Title = "Original" };

    // Act 1 - Create
    await _service.CreateDocumentAsync(document);

    // Assert 1 - Verify creation
    var created = await _service.GetDocumentAsync(document.Id);
    created.Should().NotBeNull();
    created.Title.Should().Be("Original");

    // Act 2 - Update
    created.Title = "Updated";
    await _service.UpdateDocumentAsync(created);

    // Assert 2 - Verify update
    var updated = await _service.GetDocumentAsync(document.Id);
    updated.Title.Should().Be("Updated");

    // Act 3 - Delete
    await _service.DeleteDocumentAsync(document.Id);

    // Assert 3 - Verify deletion
    var deleted = await _service.GetDocumentAsync(document.Id);
    deleted.Should().BeNull();
}
```

## Integration vs Unit Tests

### When to Use Integration Tests

**Prefer integration tests for:**
- Database operations
- Multi-component workflows
- API endpoints
- Job system operations
- External service interactions

```csharp
[Fact]
public async Task ImportJob_ProcessesDocumentsEndToEnd()
{
    // Arrange - Real database, real services
    var job = await CreateImportJobAsync();
    var handler = new ImportJobHandler(_dataSource, _fileStorage, _solrClient);

    // Act - Execute full workflow
    await handler.ExecuteAsync(job, CancellationToken.None);

    // Assert - Verify end result
    var documents = await _repository.GetDocumentsByJobAsync(job.Id);
    documents.Should().HaveCount(10);
    documents.Should().AllSatisfy(d => d.Status.Should().Be(DocumentStatus.Indexed));
}
```

### When to Use Unit Tests

**Use unit tests for:**
- Pure logic without dependencies
- Complex algorithms
- Validation logic
- Utility functions

```csharp
[Theory]
[InlineData("test.pdf", ".pdf")]
[InlineData("document.DOCX", ".docx")]
[InlineData("file", "")]
public void GetFileExtension_ReturnsCorrectExtension(string fileName, string expected)
{
    // Arrange & Act
    string extension = FileUtility.GetFileExtension(fileName);

    // Assert
    extension.Should().Be(expected);
}
```

## Test Data Management

### Always Clean Up Test Data

**Track and clean up modifications:**

```csharp
public class DocumentTests : IAsyncLifetime
{
    private readonly List<int> _createdDocumentIds = new();
    private readonly List<int> _createdFolderIds = new();

    [Fact]
    public async Task CreateDocument_AddsToFolder()
    {
        // Arrange
        int folderId = await CreateTestFolderAsync();
        _createdFolderIds.Add(folderId); // Track for cleanup

        var document = new Document { Title = "Test", FolderId = folderId };

        // Act
        await _service.CreateDocumentAsync(document);
        _createdDocumentIds.Add(document.Id); // Track for cleanup

        // Assert
        var result = await _service.GetDocumentAsync(document.Id);
        result.Should().NotBeNull();
    }

    public async Task DisposeAsync()
    {
        // Clean up in reverse order of creation
        foreach (int docId in _createdDocumentIds)
        {
            await _repository.DeleteDocumentAsync(docId);
        }

        foreach (int folderId in _createdFolderIds)
        {
            await _repository.DeleteFolderAsync(folderId);
        }
    }
}
```

### Use Test Fixtures for Shared Data

```csharp
public class DocumentTestFixture : IAsyncLifetime
{
    public TestDatabase TestDb { get; private set; }
    public int TestRepositoryId { get; private set; }
    public int TestUserId { get; private set; }

    public async Task InitializeAsync()
    {
        TestDb = new TestDatabase("test_documents");
        await TestDb.CreateAsync();

        // Seed common test data
        TestRepositoryId = await TestDb.SeedRepositoryAsync();
        TestUserId = await TestDb.SeedUserAsync();
    }

    public async Task DisposeAsync()
    {
        await TestDb.DropAsync();
    }
}

// Use in tests
public class DocumentTests : IClassFixture<DocumentTestFixture>
{
    private readonly DocumentTestFixture _fixture;

    public DocumentTests(DocumentTestFixture fixture)
    {
        _fixture = fixture;
    }

    [Fact]
    public async Task Test_UsesFixtureData()
    {
        // Use _fixture.TestRepositoryId, etc.
    }
}
```

### Isolation Between Tests

**Each test should be independent:**

```csharp
// Good - Test creates its own data
[Fact]
public async Task DeleteDocument_RemovesDocument()
{
    // Arrange - Create specific test data
    var document = await CreateTestDocumentAsync("Test");

    // Act
    await _service.DeleteDocumentAsync(document.Id);

    // Assert
    var result = await _service.GetDocumentAsync(document.Id);
    result.Should().BeNull();
}

// Bad - Test depends on external data
[Fact]
public async Task DeleteDocument_RemovesDocument()
{
    // Assumes document with ID 1 exists - fragile!
    await _service.DeleteDocumentAsync(1);
}
```

## Common Testing Patterns

### FluentAssertions

**Use FluentAssertions for readable assertions:**

```csharp
// Collections
documents.Should().HaveCount(5);
documents.Should().Contain(d => d.Title == "Test");
documents.Should().AllSatisfy(d => d.Status.Should().Be(DocumentStatus.Active));

// Null checks
document.Should().NotBeNull();
document!.Title.Should().NotBeNullOrEmpty();

// Numeric comparisons
count.Should().BeGreaterThan(0);
count.Should().BeLessThanOrEqualTo(100);

// String comparisons
title.Should().Be("Expected");
title.Should().Contain("substring");
title.Should().StartWith("prefix");

// DateTime comparisons
timestamp.Should().BeCloseTo(DateTime.UtcNow, TimeSpan.FromSeconds(5));
timestamp.Should().BeAfter(startTime);

// Exceptions
Func<Task> act = async () => await _service.InvalidOperationAsync();
await act.Should().ThrowAsync<InvalidOperationException>()
    .WithMessage("*expected message*");

// Object comparisons
result.Should().BeEquivalentTo(expected, options => options
    .Excluding(d => d.Id)
    .Excluding(d => d.DateCreated));
```

### Testing Async Code

**Always await async operations in tests:**

```csharp
[Fact]
public async Task AsyncMethod_ReturnsExpectedResult()
{
    // Act
    var result = await _service.GetDataAsync();

    // Assert
    result.Should().NotBeNull();
}

// Don't use .Result or .Wait() - causes deadlocks
```

### Testing Exceptions

```csharp
[Fact]
public async Task DeleteDocument_ThrowsException_WhenNotFound()
{
    // Arrange
    int nonExistentId = 999999;

    // Act
    Func<Task> act = async () => await _service.DeleteDocumentAsync(nonExistentId);

    // Assert
    await act.Should().ThrowAsync<DocumentNotFoundException>()
        .WithMessage("*999999*");
}
```

### Theory Tests for Multiple Cases

```csharp
[Theory]
[InlineData("", false)]
[InlineData("   ", false)]
[InlineData("a", true)]
[InlineData("Valid Title", true)]
public void IsValidTitle_ReturnsExpectedResult(string title, bool expected)
{
    // Act
    bool result = DocumentValidator.IsValidTitle(title);

    // Assert
    result.Should().Be(expected);
}

// For complex data
public static IEnumerable<object[]> DocumentTestData =>
    new List<object[]>
    {
        new object[] { new Document { Title = "Test1" }, true },
        new object[] { new Document { Title = "" }, false },
    };

[Theory]
[MemberData(nameof(DocumentTestData))]
public void ValidateDocument_ReturnsExpectedResult(Document doc, bool expected)
{
    // Act & Assert
    DocumentValidator.IsValid(doc).Should().Be(expected);
}
```

## Playwright vs Selenium

### Prefer Playwright for New Tests

**Playwright advantages:**
- Faster and more reliable
- Better async/await support
- Auto-wait for elements
- Better debugging tools
- Modern API

**Migrate Selenium tests to Playwright when:**
- Adding new features to tested areas
- Fixing flaky Selenium tests
- Major test refactoring

### Playwright Example

```csharp
[TestCaseId(12345)]
public class DocumentListTests : PageTest
{
    [Test]
    public async Task DocumentList_DisplaysDocuments()
    {
        // Arrange
        await Page.GotoAsync("/documents");
        await Page.WaitForLoadStateAsync(LoadState.NetworkIdle);

        // Act
        var documentRows = await Page.Locator(".document-row").AllAsync();

        // Assert
        documentRows.Should().HaveCountGreaterThan(0);
        await Expect(Page.Locator(".document-row").First)
            .ToContainTextAsync("Test Document");
    }

    [Test]
    public async Task SelectDocument_ShowsDetails()
    {
        // Arrange
        await Page.GotoAsync("/documents");

        // Act
        await Page.ClickAsync(".document-row:first-child");
        await Page.WaitForSelectorAsync(".document-details");

        // Assert
        await Expect(Page.Locator(".document-details .title"))
            .ToBeVisibleAsync();
    }
}
```

### Selenium (Legacy)

**Only for existing tests not yet migrated:**

```csharp
[TestCaseId(12345)]
public class DocumentListTests : E2ETestBase
{
    [Fact]
    public void DocumentList_DisplaysDocuments()
    {
        // Arrange
        Driver.Navigate().GoToUrl($"{BaseUrl}/documents");
        Wait.Until(d => d.FindElement(By.ClassName("document-row")));

        // Act
        var documentRows = Driver.FindElements(By.ClassName("document-row"));

        // Assert
        documentRows.Should().HaveCountGreaterThan(0);
    }
}
```

## API Testing

### API Test Structure

```csharp
public class DocumentApiTests : ApiTestBase
{
    private readonly DocumentApiClient _client;
    private readonly List<int> _createdDocumentIds = new();

    public DocumentApiTests()
    {
        _client = new DocumentApiClient(HttpClient);
    }

    [Fact]
    public async Task GetDocuments_ReturnsDocuments()
    {
        // Arrange
        await SeedTestDocumentsAsync(5);

        // Act
        var response = await _client.GetDocumentsAsync();

        // Assert
        response.Should().NotBeNull();
        response.Documents.Should().HaveCountGreaterOrEqualTo(5);
    }

    [Fact]
    public async Task CreateDocument_ReturnsCreated()
    {
        // Arrange
        var request = new CreateDocumentRequest
        {
            Title = "Test Document",
            RepositoryId = TestRepositoryId
        };

        // Act
        var response = await _client.CreateDocumentAsync(request);

        // Assert
        response.Should().NotBeNull();
        response.Id.Should().BeGreaterThan(0);
        _createdDocumentIds.Add(response.Id); // Track for cleanup

        // Verify document was actually created
        var document = await _client.GetDocumentAsync(response.Id);
        document.Title.Should().Be(request.Title);
    }

    [Fact]
    public async Task DeleteDocument_Returns404_WhenNotFound()
    {
        // Arrange
        int nonExistentId = 999999;

        // Act
        Func<Task> act = async () => await _client.DeleteDocumentAsync(nonExistentId);

        // Assert
        await act.Should().ThrowAsync<ApiException>()
            .Where(e => e.StatusCode == 404);
    }

    public override async Task DisposeAsync()
    {
        // Clean up created documents
        foreach (int id in _createdDocumentIds)
        {
            try
            {
                await _client.DeleteDocumentAsync(id);
            }
            catch
            {
                // Ignore cleanup failures
            }
        }

        await base.DisposeAsync();
    }
}
```

### TestCaseId Attribute

**Link tests to Azure DevOps work items:**

```csharp
[TestCaseId(12345)]
public class DocumentTests
{
    [TestCaseId(12346)]
    [Fact]
    public async Task CreateDocument_AddsDocument()
    {
        // Test implementation
    }
}
```

## Testing Checklist

When reviewing tests, verify:

- [ ] AAA pattern followed (or multiple Act-Assert cycles for complex scenarios)
- [ ] Test names follow convention: `MethodName_ExpectedBehavior_Condition`
- [ ] Tests use real dependencies (Docker) not in-memory providers
- [ ] FluentAssertions used for assertions
- [ ] Async/await used properly (no .Result or .Wait())
- [ ] Test data is created and cleaned up
- [ ] Tests are independent (don't rely on execution order)
- [ ] TestCaseId attributes present linking to work items
- [ ] Playwright used for new E2E tests (not Selenium)
- [ ] API tests verify both success and error cases
- [ ] Exception tests use `Should().ThrowAsync<>()`
- [ ] No hardcoded test data (create data in test setup)
- [ ] Tests focus on behavior, not implementation details

## Common Anti-Patterns

### Don't Mock Everything

```csharp
// Bad - Over-mocking
var mockRepo = new Mock<IDocumentRepository>();
var mockService = new Mock<IDocumentService>();
var mockLogger = new Mock<ILogger>();
// Testing nothing real!

// Good - Use real implementations
var repository = new DocumentRepository(_testDb.DataSource);
var service = new DocumentService(repository, _logger);
```

### Don't Share Mutable State

```csharp
// Bad - Shared state
private static Document _testDocument = new() { Title = "Shared" };

[Fact]
public void Test1() => _testDocument.Title = "Modified"; // Affects Test2!

[Fact]
public void Test2() => Assert.Equal("Shared", _testDocument.Title); // Flaky!

// Good - Each test creates its own data
[Fact]
public void Test1()
{
    var document = new Document { Title = "Test1" };
    // Use document
}
```

### Don't Use Sleep/Delays

```csharp
// Bad - Flaky timing
await _service.StartAsync();
await Task.Delay(1000); // Hope it finishes in 1 second
var result = await _service.GetStatusAsync();

// Good - Poll with timeout
await _service.StartAsync();
var result = await WaitForStatusAsync(Status.Complete, TimeSpan.FromSeconds(30));
```
