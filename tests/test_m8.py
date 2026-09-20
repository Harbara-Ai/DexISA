import unittest
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import mujoco
import xml.etree.ElementTree as ET
from dex_hand.adapters import create_adapter
from dex_hand.core.outcome import AdapterError
from dex_hand.core.types import PINCH_GROUPS
from dex_hand.sim.worlds import WorldConfig
from dex_hand.sim.perturbation import MujocoPerturbation
from dex_hand.skills.shape_hand import ShapeHand
from dex_hand.skills.make_contact import MakeContact
from dex_hand.skills.establish_grasp import EstablishGrasp
from dex_hand.skills.break_contact import BreakContact
from dex_hand.modes.maintain_grasp import MaintainGrasp
from dex_hand.adapters.sharpa_mujoco import find_sharpa_asset

ROOT=Path(__file__).resolve().parents[1]


class CrossEmbodimentTests(unittest.TestCase):
    def test_missing_assets_still_explicit(self):
        with patch.dict("os.environ",{"SHARPA_MJCF":str(ROOT/"absent-sharpa.xml")}):
            with self.assertRaises(AdapterError) as ctx:create_adapter("sharpa")
        self.assertEqual(ctx.exception.failure_class,"NOT_SUPPORTED")

    def test_two_real_embodiments_same_calls(self):
        for hand in ("wuji","sharpa"):
            with self.subTest(hand=hand):
                a=create_adapter(hand)
                for skill in (ShapeHand(a),MakeContact(a),EstablishGrasp(a,MujocoPerturbation(a))):
                    out=skill.run("target",PINCH_GROUPS)
                    self.assertTrue(out.success,out.to_dict())
                observation=a.build_canonical_observation()
                self.assertEqual(observation.grasp.state.value,"STABLE")
                self.assertIsNone(observation.grasp.task_wrench_margin.value)
                self.assertIsNone(observation.interaction.object_slip.value)
                mode=MaintainGrasp(a)
                self.assertTrue(mode.enter("target",PINCH_GROUPS).success)
                a.step(375)
                self.assertTrue(mode.active,mode.query())
                out=BreakContact(a).run("target",PINCH_GROUPS)
                self.assertTrue(out.success,out.to_dict())

    def test_shared_agent_skill_and_mode_sources_unchanged(self):
        before=json.loads((ROOT/"results_cross/shared_before.json").read_text())
        for name,digest in before.items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)

    def test_sharpa_1000_steps_stable(self):
        a=create_adapter("sharpa",config=WorldConfig(kind="empty"))
        a.step(1000)
        self.assertEqual(a.model.nu,22)
        self.assertEqual(a.model.nsensor,0)
        self.assertTrue(np.isfinite(a.data.qpos).all())
        self.assertLess(np.max(np.abs(a.data.qvel)),.1)
        self.assertEqual(sum(w.number for w in a.data.warning),0)
        self.assertFalse(a.build_canonical_observation().hand.collision.value)

    def test_sharpa_effort_caps_from_official_urdf(self):
        a=create_adapter("sharpa")
        tree=ET.parse(find_sharpa_asset().with_suffix(".urdf"))
        limits={j.get("name"):float(j.find("limit").get("effort")) for j in tree.findall("joint") if j.find("limit") is not None}
        for i,j in enumerate(a.joints):
            limit=limits[a.model.joint(j).name]
            np.testing.assert_array_equal(a.model.actuator_forcerange[i],[-limit,limit])
        self.assertTrue(a.model.actuator_forcelimited.all())

    def test_sharpa_contact_pair_friction_and_no_sensor(self):
        for mu in (.2,.7,1.2):
            a=create_adapter("sharpa",config=WorldConfig(friction=mu))
            self.assertTrue(ShapeHand(a).run("target",PINCH_GROUPS).success)
            self.assertTrue(MakeContact(a).run("target",PINCH_GROUPS).success)
            pairs=[c for c in a.data.contact if a.object_geom in (c.geom1,c.geom2)
                   and a.model.geom_bodyid[c.geom1]!=0 and a.model.geom_bodyid[c.geom2]!=0]
            self.assertTrue(pairs)
            for c in pairs:self.assertAlmostEqual(c.friction[0],mu)
