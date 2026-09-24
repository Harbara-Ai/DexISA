# External hand-model assets

DexISA does not include hand XML/URDF models or meshes. Obtain each asset from its source under the source's license, preserve its companion meshes, and set the relevant environment variable to an **absolute** model XML path. The runtime checks the configured file and referenced meshes at startup. No automatic download is performed.

| Hand | Path variable | Source and pinned version used in this reference | Local license evidence | Required files |
| --- | --- | --- | --- | --- |
| Wuji Hand2 right | `WUJI_MJCF` | Local `wuji-hand2-reorient` snapshot `e254aa92fb59dd97f35e9314e8526ec770b1462b`; source XML SHA-256 `ee87511d448851c21e6e445b0ea22c1adf82febbf90fe5b6eccf4c914fbf8d81`. Public upstream URL not established here. | Snapshot has an Apache-2.0 `LICENSE`; confirm that it covers the model and meshes before redistribution. | `mjcf/right.xml` and its relative `../meshes/right/` tree. |
| Sharpa Wave right | `SHARPA_MJCF` | [sharpa-robotics/sharpa-urdf-usd-xml](https://github.com/sharpa-robotics/sharpa-urdf-usd-xml), commit `0d19cac602f46456b819e4b6a2c09a74982c9a3e`. XML SHA-256 `43d9cb63d724889b69574a5e0981aee4a2f30d825c85f3098988e3a7a3bb9980`. | Source checkout contains Apache-2.0 `LICENSE.txt` and `NOTICE.txt`; verify current upstream terms. | `right_sharpa_wave.xml`, matching `right_sharpa_wave.urdf`, and `meshes/` next to them. |
| Allegro V5 4F | `ALLEGRO_V5_MJCF` | [Wonikrobotics-git/allegro_hand_ros2_v5](https://github.com/Wonikrobotics-git/allegro_hand_ros2_v5), commit `80bd4a88d2c59b8ad0242ec3730302bde61c84fb`. | Local source checkout has BSD-2-Clause `LICENSE`; verify current upstream terms. | Generate `allegro_v5_base.xml` locally from the pinned right-B URDF, matching mesh tree, and the included profile. |
| Robotiq 2F-85 | `ROBOTIQ_2F85_MJCF` | [robotiq/ros](https://github.com/robotiq/ros), commit `8d7b8412ad685ffe1db5719da6e8fce6c1896e5e`. | Local source checkout has BSD-3-Clause `LICENSE`; verify current upstream terms. | Generate `robotiq_2f85_base.xml` locally from the pinned xacro and collision meshes. |

For Allegro and Robotiq, place the separately obtained pinned source trees under a directory containing `Wonikrobotics-git_allegro_hand_ros2_v5/` and `robotiq_ros/`. Set `DEXISA_VENDOR_ASSET_ROOT` to that directory (or use the default ignored `assets/embodiment_audit/` under the checkout), then run `python scripts/build_official_mujoco.py` from a source checkout. `DEXISA_GENERATED_MODEL_DIR` may select an external output directory. This writes generated XML under ignored `assets/embodiment_mujoco/`; it records absolute references to the local mesh files. Re-run it on each machine after placing the sources. Point `ALLEGRO_V5_MJCF` and `ROBOTIQ_2F85_MJCF` to those generated files. The builder requires both pinned source trees; no vendor files are fetched by the script.

For example, in PowerShell:

```powershell
$env:WUJI_MJCF = 'C:\models\wuji_hand2\mjcf\right.xml'
$env:SHARPA_MJCF = 'C:\models\sharpa_wave\right_sharpa_wave.xml'
$env:ALLEGRO_V5_MJCF = 'C:\models\dexisa\allegro_v5_base.xml'
$env:ROBOTIQ_2F85_MJCF = 'C:\models\dexisa\robotiq_2f85_base.xml'
```

Only configure assets for the hand you intend to run. Missing assets are a deployment issue, not evidence that a hand or Skill is physically unsupported. The packaged profiles and schema are runtime metadata, not hand geometry.
