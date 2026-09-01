from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from loose_thread_api.agents.interpreter import ThoughtInterpreter
from loose_thread_api.agents.resumption import ResumptionAgent, ResumptionEvidence
from loose_thread_api.config import Settings
from loose_thread_api.models.interpretation import CommitmentStrength, InterpretationResult

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals" / "cases.jsonl"
RESULT_PATH = ROOT / "evals" / "results" / "latest.json"
COMMITMENT_RANK = {
    CommitmentStrength.NONE: 0,
    CommitmentStrength.CURIOSITY: 1,
    CommitmentStrength.POSSIBLE: 2,
    CommitmentStrength.INTENDED: 3,
    CommitmentStrength.COMMITTED: 4,
}


@dataclass(frozen=True)
class CaseResult:
    id: str
    type: str
    passed: bool
    checks: list[str]
    trace_id: str | None = None
    response_id: str | None = None
    usage: dict[str, int] | None = None
    error_type: str | None = None


def load_cases() -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in CASES_PATH.read_text(encoding="utf-8").splitlines() if line
    ]


def check_interpretation(case: dict[str, Any], result: InterpretationResult) -> list[str]:
    expect = case["expect"]
    thoughts = result.thoughts
    checks: list[str] = []

    if len(thoughts) < expect.get("min_thoughts", 0):
        checks.append("minimum thought count")
    if len(thoughts) > expect.get("max_thoughts", 10):
        checks.append("maximum thought count")

    actual_kinds = {thought.kind.value for thought in thoughts}
    if not set(expect.get("kinds", [])).issubset(actual_kinds):
        checks.append("required thought kinds")
    if set(expect.get("forbid_kinds", [])).intersection(actual_kinds):
        checks.append("forbidden thought kinds")

    if "max_commitment" in expect:
        maximum = COMMITMENT_RANK[CommitmentStrength(expect["max_commitment"])]
        if any(COMMITMENT_RANK[thought.commitment_strength] > maximum for thought in thoughts):
            checks.append("commitment inflation")

    source = str(case["input"])
    if any(thought.raw_fragment not in source for thought in thoughts):
        checks.append("fragment provenance")
    for fragment in expect.get("literal_fragments", []):
        if not any(fragment in thought.raw_fragment for thought in thoughts):
            checks.append(f"literal fragment: {fragment}")

    temporal = [thought.temporal for thought in thoughts if thought.temporal.literal]
    combined_literals = " ".join(item.literal or "" for item in temporal)
    for literal in expect.get("temporal_literals", []):
        if literal not in combined_literals:
            checks.append(f"temporal literal: {literal}")
    if expect.get("resolved_at") is False and any(
        item.resolved_at is not None for item in temporal
    ):
        checks.append("ambiguous time resolution")
    return checks


async def run_interpreter_case(interpreter: ThoughtInterpreter, case: dict[str, Any]) -> CaseResult:
    try:
        output = await interpreter.interpret(
            raw_text=case["input"],
            timezone="America/Toronto",
            client_created_at="2026-09-01T09:00:00-04:00",
            correlation_id=str(uuid4()),
        )
        failures = check_interpretation(case, output.result)
        return CaseResult(
            id=case["id"],
            type=case["type"],
            passed=not failures,
            checks=failures or ["structured output and semantic checks passed"],
            trace_id=output.telemetry.trace_id,
            response_id=output.telemetry.response_id,
            usage=output.telemetry.usage,
        )
    except Exception as error:  # noqa: BLE001 - an eval case must record any provider failure
        return CaseResult(
            id=case["id"],
            type=case["type"],
            passed=False,
            checks=["agent invocation failed"],
            error_type=type(error).__name__,
        )


def run_schema_rejection_case(case: dict[str, Any]) -> CaseResult:
    rejected = False
    try:
        InterpretationResult.model_validate(case["input"])
    except ValidationError:
        rejected = True
    return CaseResult(
        id=case["id"],
        type=case["type"],
        passed=rejected,
        checks=[
            "malformed structured output rejected" if rejected else "malformed output accepted"
        ],
    )


async def run_resumption_case(resumption: ResumptionAgent, case: dict[str, Any]) -> CaseResult:
    evidence = [
        ResumptionEvidence(
            id=UUID(item["id"]),
            refined_text=item["refined_text"],
            relation_type=item["relation_type"],
        )
        for item in case["evidence"]
    ]
    try:
        output = await resumption.resume(
            thought_id=uuid4(),
            refined_text=case["selected"],
            evidence=evidence,
            correlation_id=str(uuid4()),
        )
        failures: list[str] = []
        allowed_ids = {item.id for item in evidence}
        citations = set(output.result.supporting_thought_ids)
        if len(citations) < case["expect"]["required_citations"]:
            failures.append("missing supporting citation")
        if not citations.issubset(allowed_ids):
            failures.append("unsupported citation")
        rendered = " ".join(
            filter(
                None,
                [
                    output.result.where_you_got_to,
                    output.result.unresolved_loop,
                    output.result.suggested_prompt,
                ],
            )
        ).lower()
        for phrase in case["expect"].get("forbidden_phrases", []):
            if phrase.lower() in rendered:
                failures.append(f"unsupported phrase: {phrase}")
        return CaseResult(
            id=case["id"],
            type=case["type"],
            passed=not failures,
            checks=failures or ["citations and faithfulness checks passed"],
            trace_id=output.telemetry.trace_id,
            response_id=output.telemetry.response_id,
            usage=output.telemetry.usage,
        )
    except Exception as error:  # noqa: BLE001 - an eval case must record any provider failure
        return CaseResult(
            id=case["id"],
            type=case["type"],
            passed=False,
            checks=["agent invocation failed"],
            error_type=type(error).__name__,
        )


async def main() -> int:
    settings = Settings()
    interpreter = ThoughtInterpreter(settings)
    resumption = ResumptionAgent(settings)
    results: list[CaseResult] = []
    for case in load_cases():
        if case["type"] == "interpreter":
            result = await run_interpreter_case(interpreter, case)
        elif case["type"] == "resumption":
            result = await run_resumption_case(resumption, case)
        else:
            result = run_schema_rejection_case(case)
        results.append(result)
        print(f"{'PASS' if result.passed else 'FAIL'} {result.id}: {', '.join(result.checks)}")

    passed = sum(result.passed for result in results)
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "models": {
            "interpreter": settings.openai_model_interpreter,
            "resumption": settings.openai_model_resumption,
        },
        "summary": {"passed": passed, "failed": len(results) - passed, "total": len(results)},
        "cases": [asdict(result) for result in results],
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Eval summary: {passed}/{len(results)} passed; results={RESULT_PATH}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
