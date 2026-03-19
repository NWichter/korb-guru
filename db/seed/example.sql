-- Postgres seed (data only). Schema is in apps/api/alembic/. Run: pnpm db:seed:postgres
-- Safe to re-run: TRUNCATE + INSERT. For production-like reference data, use INSERT ... ON CONFLICT DO UPDATE.

TRUNCATE example;
INSERT INTO example (name) VALUES
  ('Alpha'),
  ('Beta'),
  ('Gamma');
