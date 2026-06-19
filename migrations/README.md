# Database Migrations

Alembic migration files live in `versions/`.

Create a new migration with:

```powershell
alembic revision --autogenerate -m "describe change"
```

Apply migrations with:

```powershell
alembic upgrade head
```
