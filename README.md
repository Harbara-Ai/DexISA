# DexISA

DexISA is an offline MuJoCo reference runtime for semantic physical-interaction Skills across Wuji Hand2, Sharpa Wave, Allegro V5 4F, and Robotiq 2F-85. The Codex entrypoint is [.agents/skills/dexisa/SKILL.md](.agents/skills/dexisa/SKILL.md); executable Python lives in the installable `dex_hand` package. The Skill is not a substitute for installing the runtime.

## Latest experiment: Wuji GUARDED_CONTACT in MuJoCo (2026-09-20)

This is a **non-formal, single-pair Wuji GUARDED_CONTACT comparison in MuJoCo physics simulation**. Contact and object motion come from the simulated hand model and MuJoCo contact dynamics, not a scripted contact flag or a run on physical hardware. Both episodes succeeded in the same nominal scene with equivalent initial states. The Skill result is an existing instrumentation sanity run; only the Direct episode was run afterward. It is preliminary evidence, not a four-hand benchmark or a statistically supported performance claim.

| Metric | Skill sanity baseline | Direct single episode |
| --- | ---: | ---: |
| Outcome | SUCCESS | SUCCESS |
| Native input tokens | 7,216 | 49,173 |
| Native output tokens | 65 | 871 |
| Total tokens | 7,281 | 50,044 |
| Decision cycles | 2 | 7 |
| Control interventions | 1 | 5 |
| Robot tool calls | 1 | 6 |
| T_active (s) | 4.5775069 | 40.8632101 |
| T_physical (s) | 0.676 | 2.100 |

Native token usage and timing evidence are preserved in the [Skill sanity report](results_instrumentation_sanity/INSTRUMENTATION_SANITY_REPORT.md), [Direct pair report](results_wuji_contact_direct_single/WUJI_CONTACT_DIRECT_SINGLE.md), and [pair comparison JSON](results_wuji_contact_direct_single/pair_comparison.json). The [publication manifest](PUBLICATION_MANIFEST.json) records the sanitization of the archived traces; its runtime-file hashes refer to the 2026-09-20 publication snapshot, while the current runtime has since evolved. See [LEGACY_PUBLICATION.md](LEGACY_PUBLICATION.md) for measurement limitations, including differences in prompts, tool schemas, and stopping behavior; the token gap cannot be attributed solely to the Skill interface.

## Install and run

Cloning or downloading this repository gives you the **Skill instructions and runtime source**, but is not by itself enough to run a hand. You need a working Python 3.11 or newer interpreter (use an existing installation if available), Python dependencies, and the selected hand's separately obtained model and meshes. Open the cloned repository as the Codex workspace so Codex can discover its project Skill at `.agents/skills/dexisa/SKILL.md`; no separate global Skill copy is needed when working inside this repository. The Skill tells Codex how to use the bridge; it does not install or launch the runtime automatically.

On a new Windows machine, for example:

```powershell
git clone https://github.com/Harbara-Ai/DexISA.git
cd DexISA
python --version  # Confirm this is Python 3.11 or newer; install Python only if needed.
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .

# Obtain the selected hand's model and meshes separately (docs/ASSETS.md).
$env:SHARPA_MJCF = 'C:\models\sharpa_wave\right_sharpa_wave.xml'
dexisa-mujoco --hand sharpa
```

The bridge prints a `READY` JSON line when the selected scene loads. In Codex, open this `DexISA` folder and explicitly ask it to use `$dexisa` with one selected hand in offline MuJoCo. For Wuji, Allegro, or Robotiq, set the corresponding model path instead; Allegro and Robotiq also require the local model-generation step in [docs/ASSETS.md](docs/ASSETS.md). A GitHub ZIP works as source too.

The equivalent platform-neutral runtime commands are:

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

The DexISA code in this public repository has no top-level redistribution license declared yet. Public visibility does not itself grant permission to redistribute or modify the code; the owner should choose a code license before inviting downstream reuse. Vendor hand models and meshes remain external under their own license terms.
