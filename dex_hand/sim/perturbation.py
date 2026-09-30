"""Test apparatus, injected into shared controllers; not a skill sensor channel."""
import numpy as np


class MujocoPerturbation:
    def __init__(self, adapter): self.adapter = adapter

    def set_wrench(self, force=(0.,0.,0.), torque=(0.,0.,0.), frame="world"):
        if frame != "world": raise ValueError("world-frame test wrench required")
        a = self.adapter
        a.data.xfrc_applied[a.object_id,:] = np.r_[force,torque]

    def clear(self): self.set_wrench()
