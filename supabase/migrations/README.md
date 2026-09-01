# Supabase migrations

The initial migration creates the Thursday data model, pgvector/HNSW index, private audio bucket,
durable job primitives, explicit Data API grants, and owner-scoped RLS policies.

Run the local database from the repository root:

    npx --yes supabase@2.116.0 start
    npx --yes supabase@2.116.0 db reset --local
    npx --yes supabase@2.116.0 test db --local

The database reset command is the supported migration rerun path. Anonymous authentication is
enabled locally; anonymous users receive the authenticated Postgres role and are isolated by their
authenticated user ID like permanent users.
