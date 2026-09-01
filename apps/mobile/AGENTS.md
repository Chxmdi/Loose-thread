# Mobile-specific Codex instructions

- Expo + React Native + TypeScript.
- Optimize for the Thursday vertical slice, not broad app navigation.
- A capture is considered safe only after it is persisted locally; network/AI work happens afterward.
- Use invisible Supabase anonymous authentication for the demo.
- Never place Supabase service-role or OpenAI API keys in the client.
- Keep the primary flow minimal: capture -> sync status -> capacity -> <=3 cards -> start/resume -> outcome.
- Gracefully show pending enrichment instead of blocking capture.
- Add automated tests for the local capture queue and sync state machine where practical.
