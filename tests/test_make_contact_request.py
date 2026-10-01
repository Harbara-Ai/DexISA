"""Characterize intent validation, continuous termination and failure guards."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import numpy as np
from dex_hand.core.request import InstructionRequest
from dex_hand.core.types import PINCH_GROUPS
from dex_hand.core.outcome import AdapterError
from dex_hand.runtime.requests import resolve_make_contact
from dex_hand.skills.make_contact import MakeContact
from dex_hand.session_factory import create_mujoco_session
from dex_hand.core.scene import ScenePlan
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[1]

def value(x):return NS(valid=True,value=x)

class TraceAdapter:
    """Scripted observations only; no claim of physics/contact simulation."""
    dt=.1
    def __init__(self,presence,*,overload_at=None,collision_at=None,drift_at=None):
        self.presence=presence;self.overload_at=overload_at;self.collision_at=collision_at;self.drift_at=drift_at
        self.index=0;self.active_modes=[];self.events=[];self.skill='IDLE';self.phase='IDLE'
        self.commands=[];self.held=False
    def build_canonical_observation(self):
        present=self.presence[min(self.index,len(self.presence)-1)]
        contacts=[NS(object_id='target',contact_group_id=g,presence=value(True),normal_load=value(4.1 if self.index==self.overload_at else .2)) for g in present]
        obj=NS(relative_pose=value(NS(position=[.02 if self.index==self.drift_at else 0.,0.,0.])))
        return NS(timestamp=self.index*self.dt,contacts=contacts,objects={'target':obj},hand=NS(collision=value(self.index==self.collision_at)))
    def resolve_contact_group(self,group):return group
    def advance_groups(self,object_id,groups,increments):self.commands.append(tuple(increments))
    def step(self):self.index+=1
    def safe_hold(self):self.held=True

class RequestTests(unittest.TestCase):
    def request(self,args):return InstructionRequest.from_mapping({'tool':'MAKE_CONTACT','arguments':args})
    def test_legacy_uses_skill_defaults(self):
        adapter=TraceAdapter([[]])
        resolved=resolve_make_contact(self.request({}),adapter,ScenePlan(PINCH_GROUPS,.04,.012))
        self.assertEqual(resolved.contact_dwell_s,0.)
        self.assertEqual(resolved.groups,PINCH_GROUPS)
    def test_explicit_operands_and_dwell(self):
        adapter=TraceAdapter([[]])
        resolved=resolve_make_contact(self.request({'object_id':'target','contact_groups':['primary'],'termination':{'type':'contact_dwell','duration_s':.1}}),adapter,ScenePlan(PINCH_GROUPS,.04,.012))
        self.assertEqual([g.group_id for g in resolved.groups],['primary'])
        self.assertEqual(resolved.contact_dwell_s,.1)
    def test_removed_constraints_are_not_supported_without_motion(self):
        cases=[{}, {'max_normal_force_n':2.}, {'max_object_drift_m':.002}, {'max_displacement_m':.02}, {'timeout_s':5.}, {'forbid_unplanned_contact':True}]
        for fields in cases:
            adapter=TraceAdapter([[]])
            with self.subTest(fields=fields),self.assertRaises(AdapterError) as ctx:
                resolve_make_contact(self.request({'constraints':fields}),adapter,ScenePlan(PINCH_GROUPS,.04,.012))
            self.assertEqual(ctx.exception.failure_class,'NOT_SUPPORTED')
            self.assertEqual(adapter.commands,[]);self.assertEqual(adapter.index,0)
    def test_unknown_intent_is_explicit(self):
        for args in ({'speed':.1},{'contact_groups':['auxiliary']},{'constraints':{'forbid_unplanned_contact':False}},{'constraints':{'gain':1}},{'termination':{'type':'wrench_margin'}},{'termination':{'type':'contact_present','duration_s':.1}}):
            with self.subTest(args=args),self.assertRaises(AdapterError) as ctx:
                resolve_make_contact(self.request(args),TraceAdapter([[]]),ScenePlan(PINCH_GROUPS,.04,.012))
            self.assertEqual(ctx.exception.failure_class,'NOT_SUPPORTED')
    def test_bad_groups_object_and_termination_are_rejected(self):
        for args in ({'contact_groups':[]},{'contact_groups':['primary','primary']},{'contact_groups':'primary'},{'termination':{'type':'contact_dwell'}},{'termination':{'type':'contact_dwell','duration_s':False}},{'termination':{'type':'contact_dwell','duration_s':-1.}}):
            with self.subTest(args=args),self.assertRaises(ValueError):resolve_make_contact(self.request(args),TraceAdapter([[]]),ScenePlan(PINCH_GROUPS,.04,.012))
        with self.assertRaises(AdapterError) as ctx:resolve_make_contact(self.request({'object_id':'absent'}),TraceAdapter([[]]),ScenePlan(PINCH_GROUPS,.04,.012))
        self.assertEqual(ctx.exception.failure_class,'PRECONDITION_FAILED')
    def test_request_snapshot_and_envelope(self):
        raw={'tool':'MAKE_CONTACT','arguments':{'termination':{'type':'contact_dwell','duration_s':.1}}}
        req=InstructionRequest.from_mapping(raw);raw['arguments']['termination']['duration_s']=.2
        self.assertEqual(req.arguments['termination']['duration_s'],.1)
        for bad in ([],{'tool':[]},{'tool':'MAKE_CONTACT','arguments':[]},{'tool':'MAKE_CONTACT','controller':1}):
            with self.subTest(bad=bad),self.assertRaises((ValueError,AdapterError)):InstructionRequest.from_mapping(bad)
    def test_continuous_contact_dwell_resets_after_loss(self):
        both=['primary','opposition'];a=TraceAdapter([[],both,[],both,both,both])
        out=MakeContact(a).run('target',PINCH_GROUPS,contact_dwell_s=.15)
        self.assertTrue(out.success,out.to_dict());self.assertEqual(a.index,5)
        self.assertGreaterEqual(out.achieved_state['contact_dwell_s'],.15)
    def test_legacy_contact_returns_at_first_event(self):
        a=TraceAdapter([[],['primary','opposition']])
        out=MakeContact(a).run('target',PINCH_GROUPS)
        self.assertTrue(out.success);self.assertEqual(a.index,1)
        self.assertNotIn('contact_dwell_s',out.achieved_state)
    def test_dwell_keeps_force_collision_and_drift_guards(self):
        for kwargs,expected in (({'overload_at':2},'WRENCH_LIMIT_EXCEEDED'),({'collision_at':2},'COLLISION'),({'drift_at':2},'OBJECT_DISPLACED')):
            a=TraceAdapter([[],['primary','opposition']],**kwargs)
            out=MakeContact(a).run('target',PINCH_GROUPS,contact_dwell_s=1.)
            self.assertEqual(out.failure_class,expected);self.assertTrue(a.held)
    def test_dwell_deadline_and_nonparticipating_contact(self):
        a=TraceAdapter([['primary','opposition']])
        out=MakeContact(a).run('target',PINCH_GROUPS,contact_dwell_s=1.,timeout=.3)
        self.assertEqual(out.failure_class,'TIMEOUT')
        a=TraceAdapter([['primary','auxiliary']])
        self.assertEqual(MakeContact(a).run('target',PINCH_GROUPS).failure_class,'PREMATURE_CONTACT')
    def test_active_mode_conflict_remains_transactional(self):
        a=TraceAdapter([[]]);a.active_modes=['MAINTAIN_GRASP']
        out=MakeContact(a).run('target',PINCH_GROUPS,contact_dwell_s=.1)
        self.assertEqual(out.failure_class,'PRECONDITION_FAILED');self.assertEqual(a.index,0)
    def test_schema_tooling_and_packaged_contract_match(self):
        from scripts.extract_instruction_schemas import extracts
        for name,schema in extracts().items():
            Draft202012Validator.check_schema(schema)
            self.assertEqual(schema,json.loads((ROOT/'spec/instructions'/(name+'.schema.json')).read_text(encoding='utf-8')))

class PhysicsRequestTests(unittest.TestCase):
    def test_four_bootstraps_execute_same_dwell_request(self):
        for hand in ('wuji','sharpa','allegro_v5','robotiq_2f85'):
            with self.subTest(hand=hand):
                session=create_mujoco_session(hand)
                try:
                    self.assertEqual(session.execute({'tool':'SHAPE_HAND'})['skill_outcome']['status'],'SUCCESS')
                    response=session.execute({'tool':'MAKE_CONTACT','arguments':{'object_id':'target','contact_groups':[g.group_id for g in session.scene_plan.groups],'termination':{'type':'contact_dwell','duration_s':.1}}})
                    self.assertEqual(response['skill_outcome']['status'],'SUCCESS',response)
                    self.assertGreaterEqual(response['skill_outcome']['achieved_state']['contact_dwell_s'],.1)
                    self.assertGreater(session.adapter.data.ncon,0)
                    self.assertEqual(sum(w.number for w in session.adapter.data.warning),0)
                finally:session.close()
    def test_invalid_request_does_not_change_physical_state(self):
        session=create_mujoco_session('wuji')
        try:
            q=session.adapter.data.qpos.copy();time=session.adapter.data.time
            with self.assertRaises(AdapterError) as ctx:session.execute({'tool':'MAKE_CONTACT','arguments':{'constraints':{}}})
            self.assertEqual(ctx.exception.failure_class,'NOT_SUPPORTED')
            np.testing.assert_array_equal(q,session.adapter.data.qpos);self.assertEqual(time,session.adapter.data.time)
        finally:session.close()
