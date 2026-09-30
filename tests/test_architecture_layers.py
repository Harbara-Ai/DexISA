import ast,importlib,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class LayerTests(unittest.TestCase):
    def test_runtime_does_not_depend_on_evaluation(self):
        for folder in ('core','skills','modes','runtime','bridge'):
            for path in (ROOT/'dex_hand'/folder).glob('*.py'):
                for node in ast.walk(ast.parse(path.read_text())):
                    modules=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
                    for name in modules:self.assertFalse(name.startswith(('evaluation','pilot')),str(path))
    def test_legacy_evaluation_aliases_preserve_identity(self):
        for old,new in (('pilot.interfaces','evaluation.runners.episode'),('pilot.protocol','evaluation.agents.protocol'),('pilot.run','evaluation.runners.pilot')):
            self.assertIs(importlib.import_module(old),importlib.import_module(new))
    def test_bridge_does_not_construct_skills(self):
        tree=ast.parse((ROOT/'dex_hand/bridge/mujoco_adapter.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):self.assertFalse((node.module or '').startswith(('dex_hand.skills','dex_hand.adapters','dex_hand.modes')))

    def test_point_failure_state_and_result_are_json_serializable(self):
        import json,tempfile
        from evaluation.runners.episode import PilotEpisode
        with tempfile.TemporaryDirectory() as folder:
            ep=PilotEpisode('A','wuji','DIRECT_AGENT','nominal',folder)
            try:
                ep.dispatch('get_state',{'wait_s':.02})
                json.dumps(ep.compact())
                result=ep.finish('failure')
                self.assertIs(type(result['physical_success']),bool)
                json.dumps(result)
            finally:
                if not ep.trace.closed:ep.trace.close()
