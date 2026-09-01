# Codex: Start Here

## Primary instruction
Read [`CODEX_MASTER_PROMPT.md`](./CODEX_MASTER_PROMPT.md), then follow it as the implementation contract for the Thursday demo.

## Execution control plane
Use these sources in this order:

1. `AGENTS.md` — repository-wide invariants and working rules.
2. `CODEX_MASTER_PROMPT.md` — autonomous execution contract.
3. GitHub issue **#13** — Thursday command center and issue order.
4. `THURSDAY_STATUS.md` — live truth about what is actually complete.
5. `docs/exec-plans/active/THURSDAY-DEMO.md` — detailed deadline plan.
6. `docs/product-specs/PRD-v1.md` — indexed product source of truth; load only relevant sections.
7. `ARCHITECTURE.md` — system boundaries.

The goal is not to produce scaffolding or another plan. The goal is to get the real Thursday end-to-end path working against real Supabase/OpenAI services as soon as credentials are available.

Begin with issue **#1**, then **#3**, then **#5**. Build the durable jobs worker before adding multiple agents. Mobile shell/local persistence may proceed in parallel, but backend contracts remain authoritative.

After every meaningful milestone:
- run relevant checks;
- update `THURSDAY_STATUS.md`;
- update/close the corresponding GitHub issue only when acceptance criteria are actually satisfied;
- immediately continue to the next unblocked P0 item.

Do not mark completion while `make demo-smoke` fails. Before feature freeze, the real smoke path must pass twice consecutively.
