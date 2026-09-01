from __future__ import annotations

import json
import sys
import time

from demo_client import ROOT, DemoClient, DemoEnvironment

STATE_PATH = ROOT / ".failure-state.json"
RAW_TEXT = "Spend 15 minutes preserving this capture while processing is unavailable."


def retain() -> None:
    client = DemoClient(DemoEnvironment.load())
    try:
        client.health()
        client.sign_in_anonymously()
        capture_id, _ = client.create_capture(RAW_TEXT)
        time.sleep(3)
        capture = client.api("GET", f"/v1/captures/{capture_id}", expected=200)
        jobs = client.api("GET", "/v1/debug/jobs", expected=200)
        if capture["raw_text"] != RAW_TEXT or capture["processing_status"] != "queued":
            raise RuntimeError("Capture did not remain raw and queued while the worker was paused")
        if len(jobs) != 1 or jobs[0]["status"] != "queued":
            raise RuntimeError("Durable job did not remain retryable while the worker was paused")
        STATE_PATH.write_text(
            json.dumps(
                {
                    "user_id": client.user_id,
                    "access_token": client.access_token,
                    "capture_id": capture_id,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(
            "PASS capture retained raw with a queued durable job while processing was unavailable"
        )
    finally:
        client.close()


def recover() -> None:
    if not STATE_PATH.exists():
        raise RuntimeError(f"Failure demo state does not exist: {STATE_PATH}")
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    client = DemoClient(DemoEnvironment.load())
    try:
        client.use_session(access_token=state["access_token"], user_id=state["user_id"])
        capture = client.wait_capture(state["capture_id"])
        client.wait_jobs()
        if capture["raw_text"] != RAW_TEXT or not capture["thoughts"]:
            raise RuntimeError("Retained capture did not recover through processing")
        STATE_PATH.unlink()
        print("PASS the same retained capture recovered through real processing")
    finally:
        client.close()


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"retain", "recover"}:
        print("Usage: failure_demo.py retain|recover")
        return 2
    try:
        retain() if sys.argv[1] == "retain" else recover()
    except Exception as error:  # noqa: BLE001 - CLI boundary converts failures to exit status
        print(f"FAIL {type(error).__name__}: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
