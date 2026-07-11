## PIP Testing-Adjacent Guidelines

Never use `.Result` or `.Wait()` in test code — same deadlock risk as production code; always `await`.

Tests that create or update an entity implementing `IConcurrencyEntity` (e.g. `PIP_Task`) need to account for `RowVersion` — a stale or missing `RowVersion` on an update call will throw a concurrency exception, not silently succeed.
