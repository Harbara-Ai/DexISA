from .wuji_mujoco import WujiMuJoCoAdapter
from .sharpa_mujoco import SharpaMuJoCoAdapter


def create_adapter(hand, **kwargs):
    registry = {"wuji": WujiMuJoCoAdapter, "sharpa": SharpaMuJoCoAdapter}
    return registry[hand](**kwargs)
