"""Simulation-only JSONL transport: parse, invoke runtime, serialize."""
import argparse
import json
import sys
from dex_hand.core.request import InstructionRequest
from dex_hand.core.outcome import AdapterError
from dex_hand.session_factory import create_mujoco_session, SCENE_PLANS

# Retain the existing bridge startup convenience; runtime construction is injected.
Session = create_mujoco_session

def emit(value):
    print(json.dumps(value, ensure_ascii=False, default=str), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hand", required=True, choices=tuple(SCENE_PLANS))
    hand = parser.parse_args().hand
    try:
        session = create_mujoco_session(hand)
    except (AdapterError, FileNotFoundError, ValueError) as exc:
        emit({"status": "FAILED", "failure_class": getattr(exc, "failure_class", "NOT_SUPPORTED"),
              "failure_detail": str(exc), "embodiment": hand})
        return 1
    emit({"status": "READY", "embodiment": hand, "backend": "mujoco",
          "capabilities": session.adapter.get_capabilities()})
    try:
        for line in sys.stdin:
            try:
                response = session.execute(InstructionRequest.from_mapping(json.loads(line)))
            except (AdapterError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                response = {"status": "FAILED", "failure_class": getattr(exc, "failure_class", "PRECONDITION_FAILED"),
                            "failure_detail": str(exc)}
            except Exception as exc:
                session.adapter.safe_hold()
                response = {"status": "FAILED", "failure_class": "SIMULATION_ERROR",
                            "failure_detail": f"{type(exc).__name__}: {exc}"}
            emit(response)
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
