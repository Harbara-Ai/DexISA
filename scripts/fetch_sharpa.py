"""Download a pinned official model and its meshes, with provenance/hash manifest."""
import hashlib
import json
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

COMMIT = "0d19cac602f46456b819e4b6a2c09a74982c9a3e"
REPO = "sharpa-robotics/sharpa-urdf-usd-xml"
ROOT = Path(__file__).resolve().parents[1] / "assets/sharpa"


def main():
    base = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/"
    manifest = {"repository": f"https://github.com/{REPO}", "commit": COMMIT, "files": []}
    def fetch(remote, local):
        target = ROOT / local
        target.parent.mkdir(parents=True, exist_ok=True)
        data = urllib.request.urlopen(base + remote, timeout=60).read()
        target.write_bytes(data)
        manifest["files"].append({"path": local, "source": base+remote, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        return data
    prefix = "wave_01/right_sharpa_wave/"
    xml = fetch(prefix+"right_sharpa_wave.xml", "right_sharpa_wave.xml")
    fetch(prefix+"right_sharpa_wave.urdf", "right_sharpa_wave.urdf")
    for mesh in ET.fromstring(xml).findall("asset/mesh"):
        name = mesh.get("file")
        fetch(prefix+"meshes/"+name, "meshes/"+name)
    for name in ("LICENSE.txt", "NOTICE.txt", "README.md"):
        fetch(name, name)
    (ROOT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(f"Fetched {len(manifest['files'])} files at {COMMIT}")


if __name__ == "__main__": main()
