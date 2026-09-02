# Loose Thread Thursday Demo Runbook

**Demo date:** Thursday, September 3, 2026  
**Feature freeze:** Wednesday night, September 2, 2026

The configured hosted Supabase project is migrated, anonymous sign-ins are enabled, and all 13
hosted pgTAP RLS assertions pass. The zero-cost deployment runs the API on Render's free web plan
and runs the durable worker locally against hosted Supabase.

## Required Environment

Server-only values:

```text
ENVIRONMENT=production
DATABASE_URL=<Supabase direct or session-pooler Postgres URL>
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_PUBLISHABLE_KEY=<publishable key; legacy SUPABASE_ANON_KEY also works>
OPENAI_API_KEY=<server key>
CORS_ORIGINS=http://localhost:8081,http://127.0.0.1:8081
```

Smoke runner values:

```text
DEMO_API_URL=https://<deployed-api-host>
DEMO_SUPABASE_URL=https://<project-ref>.supabase.co
DEMO_SUPABASE_ANON_KEY=<publishable/anon key>
SUPABASE_SECRET_KEY=<only required by make demo-reset; legacy service-role also works>
```

Never put `OPENAI_API_KEY`, `DATABASE_URL`, or `SUPABASE_SERVICE_ROLE_KEY` in Expo variables.

## Local Start

Start Docker Desktop, then run from the repository root:

```powershell
$env:Path = "$([Environment]::GetEnvironmentVariable('Path','Machine'));$([Environment]::GetEnvironmentVariable('Path','User'))"
npx --yes supabase@2.116.0 start
npx --yes supabase@2.116.0 db reset
make backend-install
```

Load local Supabase values into each PowerShell terminal without writing them to disk:

```powershell
$values = @{}
npx --yes supabase@2.116.0 status -o env | ForEach-Object {
  if ($_ -match '^([^=]+)="?(.*?)"?$') { $values[$matches[1]] = $matches[2].TrimEnd('"') }
}
$env:DATABASE_URL = $values.DB_URL
$env:SUPABASE_URL = $values.API_URL
$env:SUPABASE_ANON_KEY = $values.ANON_KEY
$env:DEMO_SUPABASE_URL = $values.API_URL
$env:DEMO_SUPABASE_ANON_KEY = $values.ANON_KEY
$env:SUPABASE_SERVICE_ROLE_KEY = $values.SERVICE_ROLE_KEY
$env:DEMO_API_URL = 'http://127.0.0.1:8000'
```

Run the API and worker in separate terminals:

```powershell
make backend-dev
uv run --directory services/api python -m loose_thread_api.orchestration
```

Expected health response at `http://127.0.0.1:8000/health`:

```json
{"status":"ok","service":"loose-thread-api"}
```

## Deployment

1. Confirm anonymous sign-ins remain enabled on the configured dedicated Supabase project.
2. Confirm `npx supabase db push --db-url <DATABASE_URL> --dry-run --yes` reports no pending
   migrations.
3. Deploy the repository's `render.yaml` Blueprint. It creates only the free `loose-thread-api`
   web service; this avoids provisioning Render's paid background-worker plan.
4. Set the server-only values above on the API service. Render supplies `PORT`.
5. Set `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL`, and
   `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` for the mobile build.
6. In a local terminal at the repository root, run `make hosted-worker`. It reads the hosted
   `DATABASE_URL`, Supabase values, and `OPENAI_API_KEY` from the ignored `.env`.
7. Verify the deployed `/health`, Render API logs, and local worker job claims before seeding.

Production startup fails with a list of missing credential names. The Docker image was verified to
serve `/health` on a nondefault `PORT=9123`.

## Demo Data

The corpus uses synthetic text and a real anonymous Auth user. Its session state is stored only in
ignored `.demo-state.json`.

```powershell
make demo-seed
make demo-reset
```

`make demo-reset` deletes the anonymous Auth user through the admin API; ownership cascades remove
the corpus. No key, token, user record, or generated result is committed.

## Smoke Gate

```powershell
make backend-check
make eval
make demo-smoke
make demo-smoke
```

Each smoke run creates a fresh anonymous user and proves:

```text
health -> auth -> two captures -> durable jobs -> Interpreter -> embeddings -> Continuity
-> deterministic <=3 retrieval -> persisted scores -> grounded Resumption -> session
-> spawned thought -> outcome -> RLS-visible feedback -> durable calibration
-> learned preference consumed by the next retrieval
```

Expected final lines include nine `PASS` stages followed by `Demo smoke passed`. Redacted evidence
is written to ignored `e2e/results/latest.json`. The Thursday gate counts only when both consecutive
runs target `DEMO_API_URL` and `DEMO_SUPABASE_URL` for the deployed services.

## Failure Proof

Pause the worker, then run:

```powershell
make demo-failure-retain
```

It must report that raw capture evidence and its durable job remain queued. Restart the worker and
run:

```powershell
make demo-failure-recover
```

The exact same capture must complete real processing. The Expo Playwright smoke separately proves a
text capture remains in local storage across backend failure and page restart.

## Demo Script

1. Open the capture-first app and enter the first 15-minute recommendation-model thought.
2. Show immediate local save, then the capture/job/agent diagnostics.
3. Enter the related continuation and show the persisted Continuity run.
4. Choose 15 minutes and show at most three code-ranked cards plus score diagnostics.
5. Select the related open loop and show the Resumption summary with evidence IDs.
6. Start the session, choose `Something new came up`, and capture the continuation.
7. Show `session_completed`, `thought_spawned`, and retrieval feedback events.
8. Open diagnostics and show the succeeded `apply_feedback_calibration` jobs plus the
   `feedback_calibration` observation count. Request another fit and show the learned
   `personal_kind_affinity` score component.
9. Use the failure proof only if time permits; do not alter code during the demo.

## Recovery

- **API unavailable:** keep the mobile capture locally, restart `loose-thread-api`, then retry sync.
- **Worker stopped:** restart `make hosted-worker`; queued jobs claim automatically.
- **OpenAI failure:** inspect `/v1/debug/jobs`; retry-wait jobs retain raw source and back off.
- **Supabase unavailable:** do not clear the local queue. Restore connectivity, then retry sync.
- **Dead job:** correct the credential/provider cause, inspect its safe error code, then requeue only
  that verified job from an authenticated operator session.
- **Bad demo corpus:** run `make demo-reset`, then `make demo-seed`.
- **Hosted outage fallback:** run the same Docker image, local Supabase, API, worker, and Expo client
  on the demo laptop. State clearly that this is fallback evidence, not the hosted completion gate.

## Freeze Checklist

- [x] Backend lint, strict types, tests, pgTAP, evals, and Docker build pass locally.
- [x] Local real-service smoke passes end to end.
- [x] Worker-pause retention and recovery proof passes.
- [x] Seed/reset commands pass without committing demo state.
- [x] Configured hosted Supabase project is migrated and anonymous auth is enabled.
- [x] Free Render API is deployed with production credentials and the local hosted worker is running.
- [x] Deployed `/health` passes.
- [x] `make demo-smoke` passes twice consecutively against the deployed API and hosted Supabase with
  the local durable worker.
- [x] Expo is pointed at deployed services and the owner-selected web target passes the real browser
  flow from local capture through session wrap and cloud diagnostics.
- [x] Feature freeze is declared; Thursday requires startup commands only and no code edits.
