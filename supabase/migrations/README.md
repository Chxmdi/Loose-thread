# Supabase migrations

Codex should create ordered SQL migrations here for the Thursday data model, pgvector indexes, storage metadata/policies, and RLS.

Every user-owned table must have RLS enabled and tested. Do not use a service-role credential to paper over missing user policies in the app path.
