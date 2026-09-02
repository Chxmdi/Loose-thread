from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from demo_client import ROOT, DemoClient, DemoEnvironment

RESULT_PATH = ROOT / "e2e" / "results" / "latest.json"
FIRST_CAPTURE = (
    "Spend no more than 15 minutes figuring out why the recommendation model treats not now "
    "like dislike."
)
SECOND_CAPTURE = (
    "Spend 15 minutes continuing the investigation into why the recommendation model treats "
    "not now like dislike: it may mean interested later."
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def step(message: str) -> None:
    print(f"PASS {message}")


def run() -> dict[str, object]:
    environment = DemoEnvironment.load()
    client = DemoClient(environment)
    evidence: dict[str, object] = {}
    try:
        health = client.health()
        require(health.get("status") == "ok", "Backend health check failed")
        step("dependency-light backend health")

        client.sign_in_anonymously()
        require(client.user_id is not None, "Anonymous Supabase user was not created")
        step("anonymous Supabase authentication")

        first_id, accepted = client.create_capture(FIRST_CAPTURE)
        require(
            accepted["processing_status"] in {"queued", "processing", "succeeded"},
            "Capture was not accepted durably",
        )
        first = client.wait_capture(first_id)
        first_jobs = client.wait_jobs()
        require(len(first_jobs) >= 3, "Initial ingestion DAG did not complete")
        step("capture retained, interpreted, embedded, and linked")

        second_id, _ = client.create_capture(SECOND_CAPTURE)
        second = client.wait_capture(second_id)
        all_jobs = client.wait_jobs()
        require(len(all_jobs) >= 6, "Related-capture ingestion DAG did not complete")
        step("second related capture completed through durable orchestration")

        runs = client.api("GET", "/v1/debug/agent-runs", expected=200)
        succeeded_names = {row["agent_name"] for row in runs if row["status"] == "succeeded"}
        require("thought_interpreter" in succeeded_names, "Interpreter run is not inspectable")
        require("continuity_agent" in succeeded_names, "Continuity run is not inspectable")
        require(
            any(
                row.get("openai_trace_id")
                for row in runs
                if row["agent_name"] == "thought_interpreter"
            ),
            "Interpreter trace ID is missing",
        )
        step("interpreter and continuity run telemetry")

        retrieval = client.api(
            "POST",
            "/v1/retrievals",
            json={"id": str(uuid4()), "window": "15", "contexts": {}},
            expected=201,
        )
        cards = retrieval["cards"]
        require(0 < len(cards) <= 3, "Retrieval did not return one to three cards")
        require(retrieval["ranking_version"] == "capacity-v1", "Unexpected ranking version")
        retrieval_debug = client.api("GET", f"/v1/debug/retrievals/{retrieval['id']}", expected=200)
        require(bool(retrieval_debug["impressions"]), "Retrieval scores were not persisted")
        require(
            all(bool(item["score_components"]) for item in retrieval_debug["impressions"]),
            "Retrieval score components are missing",
        )
        step("deterministic bounded retrieval with persisted scores")

        related_ids = {thought["id"] for thought in first["thoughts"] + second["thoughts"]}
        selected = next((card for card in cards if card["thought_id"] in related_ids), cards[0])
        resumption = client.api(
            "GET", f"/v1/thoughts/{selected['thought_id']}/resumption", expected=200
        )
        require(bool(resumption["where_you_got_to"]), "Related thought had no grounded resumption")
        require(bool(resumption["supporting_thoughts"]), "Resumption did not cite linked evidence")
        step("grounded Resumption Agent with persisted evidence IDs")

        client.api(
            "POST",
            f"/v1/retrievals/{retrieval['id']}/action",
            json={
                "action": "start",
                "thought_id": selected["thought_id"],
                "idempotency_key": f"demo-start:{retrieval['id']}",
            },
            expected=204,
        )
        session_id = str(uuid4())
        session = client.api(
            "POST",
            "/v1/sessions",
            json={
                "id": session_id,
                "thought_id": selected["thought_id"],
                "retrieval_id": retrieval["id"],
                "window": "15",
                "idempotency_key": f"demo-session:{session_id}",
            },
            expected=201,
        )
        require(session["ended_at"] is None, "Session did not start")

        completed = client.api(
            "POST",
            f"/v1/sessions/{session_id}/complete",
            json={
                "outcome": "spawned_new",
                "fit": "right",
                "actual_minutes": 12,
                "idempotency_key": f"demo-complete:{session_id}",
            },
            expected=200,
        )
        require(completed["outcome"] == "spawned_new", "Session outcome was not persisted")

        spawned_capture_id = str(uuid4())
        spawned_thought_id = str(uuid4())
        spawned = client.api(
            "POST",
            f"/v1/sessions/{session_id}/spawn",
            json={
                "capture_id": spawned_capture_id,
                "thought_id": spawned_thought_id,
                "device_id": str(uuid4()),
                "idempotency_key": f"demo-spawn:{session_id}",
                "raw_text": "Test whether interested later needs its own feedback signal.",
                "timezone": "UTC",
                "client_created_at": "2026-09-01T18:15:00Z",
            },
            expected=200,
        )
        require(
            spawned["spawned_from_thought_id"] == selected["thought_id"], "Spawn graph is incorrect"
        )
        completed_jobs = client.wait_jobs()

        session_feedback = client.rest(
            "feedback_events",
            params={"select": "event_type", "session_id": f"eq.{session_id}"},
        )
        retrieval_feedback = client.rest(
            "feedback_events",
            params={"select": "event_type", "retrieval_id": f"eq.{retrieval['id']}"},
        )
        event_types = {row["event_type"] for row in [*session_feedback, *retrieval_feedback]}
        require(
            {
                "retrieval_action",
                "session_started",
                "thought_spawned",
                "session_completed",
            }.issubset(event_types),
            f"Feedback events are incomplete: {sorted(event_types)}",
        )
        feedback_debug = client.api("GET", "/v1/debug/feedback", expected=200)
        visible_event_types = {row["event_type"] for row in feedback_debug}
        require(
            event_types.issubset(visible_event_types),
            "Authenticated feedback diagnostics omitted persisted events",
        )
        require(
            all(
                row["calibration_applied_at"] and row["calibration_version"] == "feedback-v1"
                for row in feedback_debug
                if row["event_type"] in {"retrieval_action", "session_completed"}
            ),
            "Calibrated feedback events are not inspectable",
        )
        step("session, spawned thought, outcome, and RLS-visible feedback")

        calibration_jobs = [
            row for row in completed_jobs if row["job_type"] == "apply_feedback_calibration"
        ]
        require(len(calibration_jobs) >= 2, "Feedback did not enter durable calibration jobs")
        calibration = client.api("GET", "/v1/debug/calibration", expected=200)
        require(calibration["observation_count"] >= 2, "Feedback observations were not applied")
        require(
            calibration["kind_affinity"].get(selected["kind"], 0.5) > 0.5,
            "Completed work did not increase the selected kind affinity",
        )
        require(
            calibration["duration_calibration"].get(selected["duration_bucket"], 0.0) > 0.0,
            "Right-sized work did not calibrate the selected duration",
        )

        calibrated_retrieval = client.api(
            "POST",
            "/v1/retrievals",
            json={"id": str(uuid4()), "window": "15", "contexts": {}},
            expected=201,
        )
        calibrated_debug = client.api(
            "GET",
            f"/v1/debug/retrievals/{calibrated_retrieval['id']}",
            expected=200,
        )
        selected_impression = next(
            (
                row
                for row in calibrated_debug["impressions"]
                if row["thought_id"] == selected["thought_id"]
            ),
            None,
        )
        require(selected_impression is not None, "Calibrated thought was absent from the next rank")
        require(
            selected_impression["score_components"]["personal_kind_affinity"] > 0.5,
            "The next retrieval did not consume learned affinity",
        )
        step("feedback calibration changed a subsequent retrieval score")

        final_runs = client.api("GET", "/v1/debug/agent-runs", expected=200)
        require(
            any(
                row["agent_name"] == "resumption_agent" and row["status"] == "succeeded"
                for row in final_runs
            ),
            "Resumption run telemetry is missing",
        )
        evidence = {
            "schema_version": "1.0",
            "generated_at": datetime.now(UTC).isoformat(),
            "backend": environment.api_url,
            "supabase": environment.supabase_url,
            "demo_user_id": client.user_id,
            "captures": [first_id, second_id, spawned_capture_id],
            "thought_count": len(first["thoughts"]) + len(second["thoughts"]) + 1,
            "job_count": len(client.api("GET", "/v1/debug/jobs", expected=200)),
            "agent_run_count": len(final_runs),
            "retrieval_id": retrieval["id"],
            "retrieval_card_count": len(cards),
            "resumption_agent_run_id": resumption["agent_run_id"],
            "session_id": session_id,
            "feedback_event_types": sorted(event_types),
            "feedback_debug_count": len(feedback_debug),
            "feedback_calibration_jobs": len(calibration_jobs),
            "calibration_observations": calibration["observation_count"],
            "calibrated_retrieval_id": calibrated_retrieval["id"],
            "calibrated_kind_affinity": selected_impression["score_components"][
                "personal_kind_affinity"
            ],
            "passed": True,
        }
        return evidence
    finally:
        client.close()


def main() -> int:
    try:
        result = run()
    except Exception as error:  # noqa: BLE001 - smoke boundary converts failures to exit status
        print(f"FAIL {type(error).__name__}: {error}")
        return 1
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Demo smoke passed; results={RESULT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
