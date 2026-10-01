"""Architecture injection, contract equivalence and no-Evaluation-change guards."""
import ast,hashlib,json,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace as NS
from dex_hand.core.request import InstructionRequest
from dex_hand.core.scene import ScenePlan
from dex_hand.core.types import PINCH_GROUPS
from dex_hand.core.instruction_schema import MAKE_CONTACT_SCHEMA
from dex_hand.core.outcome import AdapterError
from dex_hand.runtime.session import RuntimeSession
from dex_hand.runtime.requests import resolve_make_contact
from dex_hand.skills.make_contact import MakeContact
from jsonschema import Draft202012Validator
from test_make_contact_request import TraceAdapter

ROOT=Path(__file__).resolve().parents[1]
class Phase2Tests(unittest.TestCase):
    def test_runtime_has_no_embodiment_binding_or_backend_creation(self):
        for path in (ROOT/'dex_hand/runtime').glob('*.py'):
            source=path.read_text(encoding='utf-8');tree=ast.parse(source)
            for name in ('wuji','sharpa','allegro_v5','robotiq_2f85','create_adapter','WorldConfig','MujocoPerturbation'):
                self.assertNotIn(name,source,str(path))
            for node in ast.walk(tree):
                if isinstance(node,ast.ImportFrom):
                    self.assertFalse((node.module or '').startswith(('dex_hand.session_factory','dex_hand.sim')),str(path))
                if isinstance(node,ast.Attribute):
                    self.assertNotIn(node.attr,('data','model','qpos','qvel'),str(path))
    def test_dependency_injection_uses_supplied_binding(self):
        adapter=TraceAdapter([[]]);adapter.get_observation_capabilities=lambda:{}
        adapter.get_capabilities=lambda:{'available':True}
        plan=ScenePlan(PINCH_GROUPS,.07,.03,object_id='supplied-object')
        session=RuntimeSession(adapter=adapter,scene_plan=plan)
        self.assertIs(session.adapter,adapter);self.assertIs(session.scene_plan,plan)
        self.assertFalse(hasattr(session,'hand'))
        # The runtime does not silently substitute a hardcoded scene object.
        with self.assertRaises(AdapterError) as ctx:
            session.execute({'tool':'MAKE_CONTACT'})
        self.assertEqual(ctx.exception.failure_class,'PRECONDITION_FAILED')
        session.close()
    def test_noncontact_instruction_consumes_supplied_plan(self):
        adapter=TraceAdapter([[]]);plan=ScenePlan(PINCH_GROUPS,.07,.03,object_id='supplied-object')
        session=RuntimeSession(adapter=adapter,scene_plan=plan)
        adapter.build_canonical_observation=lambda:NS(to_dict=lambda:{'timestamp':1.25})
        with patch('dex_hand.runtime.session.ShapeHand') as shape:
            shape.return_value.run.return_value=NS()
            with patch.object(session,'_outcome',return_value={}):
                out=session.execute({'tool':'SHAPE_HAND'})
            shape.return_value.run.assert_called_once_with('supplied-object',PINCH_GROUPS,aperture=.07,clearance=.03)
            self.assertEqual(out['simulation_time_s'],1.25)
        session.close()
    def test_capability_failure_propagates_without_motion(self):
        adapter=TraceAdapter([[]]);plan=ScenePlan(PINCH_GROUPS,.04,.012)
        adapter.resolve_contact_group=lambda group:(_ for _ in ()).throw(AdapterError('NOT_SUPPORTED','group unavailable'))
        with self.assertRaises(AdapterError) as ctx:
            resolve_make_contact(InstructionRequest('MAKE_CONTACT',{'contact_groups':['primary']}),adapter,plan)
        self.assertEqual(ctx.exception.failure_class,'NOT_SUPPORTED')
        self.assertEqual(adapter.index,0);self.assertFalse(adapter.commands)
    def test_request_cannot_override_reference_defaults(self):
        from inspect import signature
        defaults=signature(MakeContact.run).parameters
        for name,expected in {'speed':.008,'max_displacement':.045,'max_load':4.,'max_object_drift':.015,'timeout':8.,'require_all_groups':True}.items():
            self.assertEqual(defaults[name].default,expected)
        adapter=TraceAdapter([[]]);plan=ScenePlan(PINCH_GROUPS,.04,.012)
        for name in ('speed','max_load','max_object_drift','max_displacement','timeout','gain'):
            with self.subTest(name=name),self.assertRaises(AdapterError) as ctx:
                resolve_make_contact(InstructionRequest('MAKE_CONTACT',{name:1}),adapter,plan)
            self.assertEqual(ctx.exception.failure_class,'NOT_SUPPORTED')
    def test_schema_matches_static_runtime_arguments(self):
        validator=Draft202012Validator(MAKE_CONTACT_SCHEMA)
        cases=[{}, {'object_id':'target','contact_groups':['primary'],'termination':{'type':'contact_present'}},
               {'termination':{'type':'contact_dwell','duration_s':.1}}, {'termination':{}},
               {'constraints':{}}, {'contact_groups':[]}, {'contact_groups':['primary','primary']},
               {'contact_groups':[{}]}, {'object_id':''}, {'approach':{}}, {'speed':.01},
               {'termination':{'type':'other'}}, {'termination':{'type':'contact_present','duration_s':.1}},
               {'termination':{'type':'contact_dwell'}}, {'termination':{'type':'contact_dwell','duration_s':0}},
               {'termination':{'type':'contact_dwell','duration_s':True}}, {'termination':{'require_all_groups':False}}]
        plan=ScenePlan(PINCH_GROUPS,.04,.012)
        for args in cases:
            with self.subTest(args=args):
                valid=validator.is_valid(args)
                try:resolve_make_contact(InstructionRequest('MAKE_CONTACT',args),TraceAdapter([[]]),plan);accepted=True
                except (AdapterError,ValueError):accepted=False
                self.assertEqual(accepted,valid)
    def test_packaged_schema_bytes_equal_canonical_schema(self):
        self.assertEqual((ROOT/'spec/instructions/make_contact.schema.json').read_bytes(),(ROOT/'dex_hand/schema/make_contact.schema.json').read_bytes())
    def test_nonfinite_dwell_decoder_extensions_rejected(self):
        for number in (float('nan'),float('inf'),-float('inf'),10**1000):
            with self.subTest(number=repr(number)[:20]),self.assertRaises(ValueError):
                resolve_make_contact(InstructionRequest('MAKE_CONTACT',{'termination':{'type':'contact_dwell','duration_s':number}}),TraceAdapter([[]]),ScenePlan(PINCH_GROUPS,.04,.012))
    def test_protected_evaluation_and_physical_sources_are_unchanged(self):
        manifest=json.loads((ROOT/'tests/fixtures/phase2_preservation.json').read_text(encoding='utf-8'))
        for name,digest in manifest['sha256'].items():
            with self.subTest(path=name):self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest)
