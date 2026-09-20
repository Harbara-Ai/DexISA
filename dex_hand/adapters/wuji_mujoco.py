"""Wuji Hand2 embodiment mapping and bounded controller configuration."""
from .mujoco_base import MuJoCoHandAdapter
from dex_hand.sim.worlds import WorldConfig, build_world, find_wuji_asset


class WujiMuJoCoAdapter(MuJoCoHandAdapter):
    def __init__(self, config=WorldConfig(), asset=None):
        mapping={"opposition":"r_thumb", "primary":"r_index_finger", "auxiliary":"r_middle_finger"}
        super().__init__(config, build_world(config,asset), mapping,
                         {k:v+"_tip" for k,v in mapping.items()}, "r_wrist",
                         "Wuji Hand2 beta2 right", str(asset or find_wuji_asset()))
