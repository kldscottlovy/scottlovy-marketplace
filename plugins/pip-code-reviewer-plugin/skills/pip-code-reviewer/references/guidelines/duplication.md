## PIP Duplication & Consolidation Guidelines

Where shared logic belongs when consolidating duplication:

- Cross-domain shared logic → `PIP.SharedBusinessLogic` (services/QueryProviders) or `PIP.Common` (enums/utility types)
- Repeated entity↔DTO mapping → a shared AutoMapper profile (`*MapperProfile` in a domain area's `Automapper/` subfolder), never duplicated inline mapping across services/controllers
- Repeated filtering/sorting/pagination logic on a QueryProvider → a shared QueryProvider extension method rather than copy-pasted LINQ across multiple QueryProviders
