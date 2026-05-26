"""One-shot migrations for the memory store.

Each migration is a standalone module callable via `python -m`. Migrations
are idempotent — re-running on a migrated store should be a no-op.
"""
