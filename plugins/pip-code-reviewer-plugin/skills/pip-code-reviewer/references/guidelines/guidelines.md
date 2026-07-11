## PIP Project Guidelines

### DTOs and Models

New DTOs are prefixed `DTO_` (e.g. `DTO_Task`, `DTO_InvoiceBatch`) and placed in `PIP.WebApiModels`, mapped to/from entities exclusively via AutoMapper profiles — never inline. Existing `PIP.WebApiModels` classes named `xxxxxxxModel.cs` are the established convention (the `DTO_` prefix is rare in existing code) — don't flag them for lacking the prefix; only apply `DTO_` naming to newly created DTOs.

For any DTO mapping to an entity implementing `IConcurrencyEntity`, **both request and response DTOs must include `RowVersion`** (`byte[]`) — a null `RowVersion` causes a concurrency failure on save.

Enums go in a folder named `Enums`. The `xxxxxxxxEnum.cs` suffix is common but not universal (e.g. `TaskStatuses.cs`, `ApprovalStatuses.cs` don't use it) — don't flag an existing enum for lacking the suffix alone.

`frontend/PipFrontend/ClientApp/src/app/core/api-resources/` is auto-generated from OpenAPI — never edit it manually.

### Layering

EF entities live in `PIP.EF/Entities/PIP/`. Services depend on `IXxxQueryProvider`, never `PIPContext` directly. New controller code should depend on `IXxxService`, not `IXxxQueryProvider` or `PIPContext` directly — this is a rule for new code, since some existing controllers already inject QueryProviders directly.
