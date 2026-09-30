import hashlib,json,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
class PreservationTests(unittest.TestCase):
    def test_preserved_physics_and_history(self):
        manifest=json.loads((ROOT/'tests/fixtures/source_preservation.json').read_text())
        for name,digest in manifest['sha256'].items():
            with self.subTest(path=name):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest)
    def test_normative_packaged_copy_matches(self):
        self.assertEqual((ROOT/'dexterous-hand-skill-mcp-spec-v0.2.md').read_bytes(),(ROOT/'dex_hand/schema/dexterous-hand-skill-mcp-spec-v0.2.md').read_bytes())
