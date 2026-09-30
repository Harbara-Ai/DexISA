# Evaluation layer

Legacy pilot tasks are A POINT, B guarded supported contact, C button press/release, D supported grasp/hold/release. These differ from the later external POINT snapshot's A-J taxonomy.

Task descriptions: tasks/definitions.py. Per-step scoring: evaluators/task_state.py. Common shield: safety/common_shield.py. Agent action surfaces/prompts: agents/. Native usage: metrics/. Scene/trace runner: runners/episode.py. API runner: runners/pilot.py.

`python -m pilot.run --prepare` remains compatible with `python -m evaluation.runners.pilot --prepare`; it freezes the existing 24 paired episodes without inference. Actual API execution still requires model/key configuration and explicit preflight_gates.json. This refactor does not run an Agent experiment.

Historical records stay at their original paths; see records/README.md. Runtime imports no evaluation modules. The old dex_hand.evaluators path is a compatibility import for external consumers, not a runtime dependency.
