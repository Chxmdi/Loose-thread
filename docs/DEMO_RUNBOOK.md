# Loose Thread — Thursday Demo Runbook

**Demo date:** Thursday, September 3, 2026  
**Feature freeze:** Wednesday night, September 2, 2026

Codex must keep this runbook synchronized with the implementation. By feature freeze it must contain exact deployed URLs/commands, environment prerequisites, reset/seed instructions, recovery steps, and verified expected outputs.

## Pre-demo gates
- [ ] All P0 implementation issues are complete.
- [ ] Required environment variables are configured outside git.
- [ ] Database migrations are applied to the demo Supabase project.
- [ ] Demo seed/reset command is documented and tested.
- [ ] Backend `/health` passes.
- [ ] Worker is running and claiming jobs.
- [ ] `make demo-smoke` passes twice consecutively against real services.
- [ ] Mobile client points to the deployed backend.
- [ ] Offline/no-loss capture fallback has been manually verified.
- [ ] No code changes are required on Thursday morning.

## Target demo story
1. Launch directly into capture.
2. Capture: “Ask Maya if the launch deck is ready, and maybe figure out why the recommendation model treats ‘not now’ like dislike.”
3. Show immediate local-save confirmation.
4. Briefly show diagnostics: capture -> durable job -> Interpreter Agent -> two structured thoughts -> embedding/linking jobs.
5. Emphasize that the first clause remains a commitment while the second stays tentative/open-loop.
6. Capture: “Actually, timing might need to be its own feature because not now can mean interested later.”
7. Show Continuity Agent linking the related thoughts.
8. Choose “I have 15 minutes.”
9. Show at most three deterministically ranked options.
10. Select the recommendation-model open loop.
11. Show Resumption Agent restoring grounded context with evidence from linked thought IDs.
12. Add a continuation thought.
13. End the session with fit/outcome feedback.
14. Show persisted feedback plus internal job/agent/retrieval diagnostics.
15. Optional reliability proof: disconnect network/model path and show capture still persists locally for later processing.

## Commands
Codex must replace placeholders with exact verified commands.

```bash
# install / run backend
make backend-install
make backend-dev

# validation
make check
make demo-smoke
```

## Recovery plan
Before feature freeze, document exact recovery for:
- backend unavailable,
- worker stopped,
- OpenAI request failure,
- Supabase connectivity failure,
- mobile device loses network,
- demo corpus needs reset,
- agent job dead-letters.

The recovery plan must preserve the core product truth: a capture is never lost merely because downstream AI/infrastructure is unavailable.
