---
key: best-practices
label: C# Best Practices
---
{{base_context}}

Review ONLY for C# Best Practices:
- Modern C# idioms (nullable reference types, pattern matching, records, etc.)
- Async/await correctness — NEVER .Result or .Wait() (deadlock risk)
- Exception handling strategies
- Resource management and IDisposable
- Thread safety and concurrency
- Memory efficiency and performance implications
- private class variables perfixed with _

#### Easy Fixes

- Value type property used as input in a controller action should be nullable, required or annotated with the JsonRequiredAttribute to avoid under-posting.

  **Example of fix.**

  ```
  Noncompliant code example
  public class Product
  {
      public int Id { get; set; }             // Noncompliant
      public string Name { get; set; }
      public int NumberOfItems { get; set; }  // Noncompliant
      public decimal Price { get; set; }      // Noncompliant
  }
  If the client sends a request without setting the NumberOfItems or Price properties, they will default to 0. In the request handler method, there’s no way to determine whether they were intentionally set to 0 or omitted by mistake.
  
  Compliant solution
  public class Product
  {
      public required int Id { get; set; }
      public string Name { get; set; }
      public int? NumberOfItems { get; set; }            // Compliant - property is optional
      [JsonRequired] public decimal Price { get; set; }  // Compliant - property must have a value
  }
  ```

  

Return findings only for this dimension. Be specific with file paths and line numbers from the diff.
