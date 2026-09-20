import ast
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/".deps"))
from dex_hand.adapters import create_adapter
from dex_hand.sim.worlds import WorldConfig
from dex_hand.core.types import PINCH_GROUPS as G, PRESS_GROUPS
from dex_hand.core.outcome import SkillOutcome, AdapterError, FailureClass as F
from dex_hand.core.observation import unknown
from dex_hand.core.schema import validate_outcome
from dex_hand.skills.shape_hand import ShapeHand
from dex_hand.skills.make_contact import MakeContact
from dex_hand.skills.apply_wrench import ApplyWrench
from dex_hand.skills.establish_grasp import EstablishGrasp
from dex_hand.skills.base import contacts, loads
from dex_hand.sim.perturbation import MujocoPerturbation
from dex_hand.modes.maintain_grasp import MaintainGrasp
from test_m4 import grasp_setup


class Contracts(unittest.TestCase):
    def test_source_actuator_limits_preserved(self):
        import mujoco
        from dex_hand.sim.worlds import find_wuji_asset
        source=mujoco.MjModel.from_xml_path(str(find_wuji_asset()))
        a=create_adapter("wuji")
        np.testing.assert_array_equal(a.model.actuator_forcerange,source.actuator_forcerange)

    def test_mode_updates_and_conflict_are_transactional(self):
        a=grasp_setup()
        mode=MaintainGrasp(a)
        self.assertTrue(mode.enter("target",G).success)
        duplicate=MaintainGrasp(a)
        self.assertFalse(duplicate.enter("target",G).success)
        self.assertIs(a.mode_controller,mode)
        self.assertFalse(mode.update(target_load=100).success)
        self.assertEqual(mode.target_load,.6)
        self.assertTrue(mode.update(target_load=.7).success)
        command=a.data.ctrl.copy()
        out=ShapeHand(a).run("target",G)
        self.assertEqual(out.failure_class,"PRECONDITION_FAILED")
        self.assertTrue(mode.active)
        np.testing.assert_array_equal(command,a.data.ctrl)

    def test_shared_code_has_no_backend_access(self):
        root=Path(__file__).resolve().parents[1]/"dex_hand"
        for folder in ("skills","modes"):
            for file in (root/folder).glob("*.py"):
                source=file.read_text(encoding="utf-8")
                for token in ("mujoco","r_thumb","r_index","geom_id","actuator_trnid"):
                    self.assertNotIn(token,source,str(file))
                for node in ast.walk(ast.parse(source)):
                    if isinstance(node,ast.Attribute):self.assertNotIn(node.attr,("data","model","qpos","qvel"),str(file))

    def test_source_schema_accepts_success_and_every_failure(self):
        validate_outcome(SkillOutcome("SUCCESS","SHAPE_HAND"))
        for f in F:validate_outcome(SkillOutcome("FAILED","TEST",f,"fault injection"))
        with self.assertRaises(ValueError):SkillOutcome("FAILED","TEST")

    def test_pair_friction_matches_requested_value(self):
        for mu in (.2,.7,1.2):
            a=create_adapter("wuji",config=WorldConfig(friction=mu))
            self.assertTrue(ShapeHand(a).run("target",G).success)
            self.assertTrue(MakeContact(a).run("target",G).success)
            pairs=[c for c in a.data.contact if a.object_geom in (c.geom1,c.geom2) and a.model.geom_bodyid[c.geom1]!=0 and a.model.geom_bodyid[c.geom2]!=0]
            self.assertTrue(pairs)
            for c in pairs:self.assertAlmostEqual(c.friction[0],mu)

    def test_exhausted_guard_cannot_claim_contact(self):
        a=create_adapter("wuji")
        ShapeHand(a).run("target",G)
        out=MakeContact(a).run("target",G,max_displacement=0)
        self.assertEqual(out.failure_class,"NO_CONTACT_FOUND")

    def test_uncertain_contact_cannot_be_zero(self):
        a=create_adapter("wuji")
        ShapeHand(a).run("target",G);MakeContact(a).run("target",G)
        o=a.build_canonical_observation()
        o.contacts[0].normal_load=unknown(o.timestamp)
        with self.assertRaises(AdapterError):loads(o,G)
        o.contacts[0].presence=unknown(o.timestamp)
        with self.assertRaises(AdapterError):contacts(o)

    def test_required_wrench_not_silently_baselined(self):
        a=create_adapter("wuji")
        ShapeHand(a).run("target",G);MakeContact(a).run("target",G)
        out=EstablishGrasp(a,MujocoPerturbation(a)).run("target",G,required_wrench_set={"frame":"world","force":[1,0,0]})
        self.assertEqual(out.failure_class,"NOT_SUPPORTED")

    def test_force_and_displacement_termination(self):
        for termination in ("force","displacement"):
            a=create_adapter("wuji",config=WorldConfig(kind="button",center=(.025,.065,.24)))
            self.assertTrue(ShapeHand(a).run("target",PRESS_GROUPS,profile="POSTURE").success)
            self.assertTrue(MakeContact(a).run("target",PRESS_GROUPS).success)
            out=ApplyWrench(a).run("target",PRESS_GROUPS,termination=termination,target_force=1.,target_displacement=.004)
            self.assertTrue(out.success,out.to_dict())
