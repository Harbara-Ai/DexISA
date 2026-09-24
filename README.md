# DexISA

DexISA is an offline MuJoCo reference runtime for semantic physical-interaction Skills across Wuji Hand2, Sharpa Wave, Allegro V5 4F, and Robotiq 2F-85. The Codex entrypoint is [.agents/skills/dexisa/SKILL.md](.agents/skills/dexisa/SKILL.md); executable Python lives in the installable `dex_hand` package. The Skill is not a substitute for installing the runtime.

## Install and run

Use Python 3.11+ in a virtual environment:

```sh
python -m pip install -e .
dexisa-mujoco --hand wuji
# Or: python -m dex_hand.bridge.mujoco_adapter --hand wuji
```

Select exactly one of `wuji`, `sharpa`, `allegro_v5`, or `robotiq_2f85`. The bridge is a persistent JSON-lines process: read its `READY` response, then send one JSON object per input line. For example, `{"tool":"describe_capabilities"}` and `{"tool":"get_state"}`. Other dispatchable operations are `SHAPE_HAND`, `MAKE_CONTACT`, `ESTABLISH_GRASP`, `MAINTAIN_GRASP`, and `BREAK_CONTACT`. The current bridge uses one supported-object scene per hand; it is not a general object or target-region interface.

**Models and meshes are external.** Before starting a hand, configure its model path as described in [docs/ASSETS.md](docs/ASSETS.md). The four environment variables are `WUJI_MJCF`, `SHARPA_MJCF`, `ALLEGRO_V5_MJCF`, and `ROBOTIQ_2F85_MJCF`. Missing model, URDF, or mesh files produce explicit startup errors. The repository does not auto-download vendor assets.

This package is simulation-only. It contains no Wuji real-hardware transport, SDK, device connection, or live control path. A successful simulated Skill outcome does not establish free-space force closure or real-hardware safety. Reproducible simulation requires the versions and source files listed in the asset guide.

## Repository contents

- `dex_hand/adapters/`: four MuJoCo Adapters and shared simulation mechanics.
- `dex_hand/core/`, `skills/`, `modes/`, `sim/`: shared ISA types, observations, controllers, and scene composition.
- `dex_hand/bridge/mujoco_adapter.py`: installable JSONL bridge and CLI.
- `.agents/skills/dexisa/`: Codex usage instructions and UI metadata.
- `scripts/build_official_mujoco.py`: local Allegro/Robotiq base-XML generator from separately obtained pinned source assets.
- `dex_hand/schema/`: packaged v0.2 result schema source.

The earlier research publication and its non-formal experiments remain in [LEGACY_PUBLICATION.md](LEGACY_PUBLICATION.md). They are historical evidence, not four-hand installation instructions.

The DexISA code in this repository has no top-level redistribution license declared yet. Before making the repository public or redistributing a release, the owner should choose a code license and review all retained historical artifacts. The repository remains private unless the owner changes its visibility.
