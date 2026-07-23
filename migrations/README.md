# Database Migrations

**Not currently in use.** Nano creates and updates its SQLite schema via
`SQLModel.metadata.create_all()` in `app/memory/db.py` at application startup.

This Alembic scaffolding is kept for a future migration to versioned schema
changes. Until then, do not run `alembic upgrade` — it will not reflect the
live schema.

When migrations are adopted:

```powershell
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Migration files will live in `versions/` (create that directory when needed).
