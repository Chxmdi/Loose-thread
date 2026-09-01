# Codex: Start Here

Read `AGENTS.md`, then execute `docs/exec-plans/active/THURSDAY-DEMO.md` in priority order.

The goal is not to produce scaffolding. The goal is to get the real Thursday end-to-end path working against real Supabase/OpenAI services as soon as credentials are available.

Begin with:
1. inspect repository and active plan;
2. update `THURSDAY_STATUS.md` with a concrete milestone breakdown;
3. implement the initial Supabase schema/RLS and backend data contracts;
4. build the durable jobs worker before adding multiple agents;
5. get one real Thought Interpreter Agent path working end to end;
6. proceed through the active plan without stopping for non-critical polish.

Do not mark completion while `make demo-smoke` fails.
