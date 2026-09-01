from __future__ import annotations

import json
import sys

from demo_client import ROOT, DemoClient, DemoEnvironment
from e2e_demo import FIRST_CAPTURE, SECOND_CAPTURE

STATE_PATH = ROOT / ".demo-state.json"


def seed() -> None:
    client = DemoClient(DemoEnvironment.load())
    try:
        client.health()
        client.sign_in_anonymously()
        capture_ids: list[str] = []
        for raw_text in (FIRST_CAPTURE, SECOND_CAPTURE):
            capture_id, _ = client.create_capture(raw_text)
            client.wait_capture(capture_id)
            client.wait_jobs()
            capture_ids.append(capture_id)
        state = {
            "user_id": client.user_id,
            "access_token": client.access_token,
            "capture_ids": capture_ids,
        }
        STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        print(f"Demo corpus ready for user {client.user_id}; state stored outside git")
    finally:
        client.close()


def reset() -> None:
    if not STATE_PATH.exists():
        raise RuntimeError(f"Demo state does not exist: {STATE_PATH}")
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    client = DemoClient(DemoEnvironment.load())
    try:
        client.delete_user(state["user_id"])
        STATE_PATH.unlink()
        print("Demo user and cascade-owned corpus deleted")
    finally:
        client.close()


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"seed", "reset"}:
        print("Usage: demo_data.py seed|reset")
        return 2
    try:
        seed() if sys.argv[1] == "seed" else reset()
    except Exception as error:  # noqa: BLE001 - CLI boundary converts failures to exit status
        print(f"FAIL {type(error).__name__}: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
