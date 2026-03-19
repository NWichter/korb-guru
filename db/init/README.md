# Postgres init (optional)

This directory is mounted into the Postgres container as `/docker-entrypoint-initdb.d/`.
Scripts here run **only when the data directory is empty** (e.g. first `db:reset` before any migration).

**Schema and seed are managed by Alembic** in `apps/api/alembic/`. After starting Postgres, run:

```bash
pnpm db:migrate
```

So we keep this folder empty (or with optional non-schema scripts). Do not put `CREATE TABLE` or seed SQL here—use migrations in `apps/api/alembic/versions/` instead.
