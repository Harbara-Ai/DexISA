import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from pilot.interfaces import PilotEpisode
from pilot.protocol import TOOLS,PROMPTS
from pilot.run import parse_usage,freeze_order


class PilotTests(unittest.TestCase):
    def test_missing_usage_never_becomes_zero(self):
        with self.assertRaises(ValueError):parse_usage({'usage':None})
        with self.assertRaises(ValueError):parse_usage({'usage':{'input_tokens':2}})
        u=parse_usage({'usage':{'input_tokens':100,'output_tokens':20,'total_tokens':120,
            'input_tokens_details':{'cached_tokens':30},'output_tokens_details':{'reasoning_tokens':10}}})
        self.assertEqual(u['total_tokens'],120) # subset counters are not added again
        self.assertEqual(u['cached_input_tokens'],30)

    def test_pairing_is_24_and_adjacent(self):
        episodes=freeze_order()['episodes'];self.assertEqual(len(episodes),24)
        for i in range(0,24,2):
            a,b=episodes[i:i+2]
            self.assertEqual((a['task'],a['hand'],a['scenario']),(b['task'],b['hand'],b['scenario']))
            self.assertEqual({a['agent'],b['agent']},{'SKILL_AGENT','DIRECT_AGENT'})

    def test_direct_has_only_four_tools_and_same_cross_hand_prompt(self):
        self.assertEqual(set(TOOLS['DIRECT_AGENT']),{'get_state','describe_hand','set_joint_targets','stop'})
        for text in PROMPTS.values():
            self.assertNotIn('Wuji',text);self.assertNotIn('Sharpa',text)

    def test_direct_batch_targets_have_no_skill_or_ik(self):
        with tempfile.TemporaryDirectory() as folder:
            ep=PilotEpisode('B','wuji','DIRECT_AGENT','nominal',folder)
            ep.a._ik=lambda *a,**k:(_ for _ in ()).throw(AssertionError('Direct called IK'))
            q=ep.a.target.copy()
            result=ep.dispatch('set_joint_targets',{'targets':{'4':float(q[4]+.01),'5':float(q[5]+.01)},'duration':.02})
            self.assertNotIn('failure',result)
            self.assertAlmostEqual(ep.a.target[4],q[4]+.01);self.assertAlmostEqual(ep.a.target[5],q[5]+.01)
            self.assertEqual(ep.dispatch('ESTABLISH_GRASP',{})['failure'],'INVALID_ARGUMENT')
            ep.finish('failure')

    def test_compact_view_omits_static_and_obeys_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            ep=PilotEpisode('B','sharpa','DIRECT_AGENT','nominal',folder)
            self.assertEqual(set(ep.compact(['contacts'])),{'time','contacts'})
            self.assertNotIn('joint_definitions',ep.compact())
            ep.finish('failure')

    def test_recovery_pose_bias_is_identical(self):
        with tempfile.TemporaryDirectory() as folder:
            episodes=[PilotEpisode('B','wuji',agent,'recovery',Path(folder)/agent) for agent in ('SKILL_AGENT','DIRECT_AGENT')]
            a,b=episodes
            np.testing.assert_array_equal(a.a.data.qpos,b.a.data.qpos)
            np.testing.assert_array_equal(a.a.build_canonical_observation().objects['target'].pose.value.position,a.nominal_center)
            self.assertEqual(a.compact(['contacts','object_relative_pose','status']),b.compact(['contacts','object_relative_pose','status']))
            for ep in episodes:ep.finish('failure')

    def test_button_relative_target_and_impossible_spring_are_common(self):
        with tempfile.TemporaryDirectory() as folder:
            targets=[]
            for hand in ('wuji','sharpa'):
                ep=PilotEpisode('C',hand,'DIRECT_AGENT','safe_failure',Path(folder)/hand)
                targets.append(ep.nominal_center-ep.a.data.xpos[ep.a.palm_id])
                self.assertEqual(ep.static()['object']['stiffness']*.008,16.)
                self.assertEqual(ep.force_limit,3.)
                ep.finish('failure')
            np.testing.assert_allclose(targets[0],targets[1],atol=1e-12)
