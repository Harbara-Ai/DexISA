"""Compose real hand assets with simple configurable benchmark objects."""
from dataclasses import dataclass
from pathlib import Path
import os
import xml.etree.ElementTree as ET
import mujoco


@dataclass(frozen=True)
class WorldConfig:
    kind: str = "grasp"
    radius: float = .020
    height: float = .025
    mass: float = .06
    friction: float = .7
    center: tuple = (.025, .065, .26)
    timestep: float = .002


def find_wuji_asset():
    configured = os.environ.get("WUJI_MJCF")
    if not configured:
        raise FileNotFoundError("Set WUJI_MJCF to the external Wuji Hand2 right.xml; model and meshes are not bundled")
    candidate = Path(configured).expanduser()
    if not candidate.is_file():
        raise FileNotFoundError(f"WUJI_MJCF model missing: {candidate}")
    return candidate.resolve()


def build_world(config=WorldConfig(), asset=None):
    if config.kind not in ("grasp", "button", "empty"):
        raise ValueError("world must be grasp, button or empty")
    if min(config.radius, config.height, config.mass, config.timestep) <= 0 or config.friction < 0:
        raise ValueError("invalid world physical parameters")
    asset = Path(asset or find_wuji_asset()).resolve()
    root = ET.parse(asset).getroot()
    compiler = root.find("compiler")
    meshdir = (asset.parent / compiler.get("meshdir", "")).resolve()
    for mesh in root.findall("asset/mesh"):
        mesh_path = meshdir / mesh.get("file", "")
        if not mesh_path.is_file():
            raise FileNotFoundError(f"Wuji mesh missing: {mesh_path}")
    compiler.set("meshdir", str(meshdir))
    option = root.find("option")
    option.set("timestep", str(config.timestep))
    option.set("integrator", "implicitfast")
    option.set("gravity", "0 0 -9.81")
    option.set("iterations", "80")
    root.find("default/joint").set("damping", ".03")
    # Fixed, finite gains; ORIGINAL actuator/joint force limits are preserved.
    for actuator in root.find("actuator"):
        actuator.set("kp", "3")
        actuator.set("kv", ".09")
    world = root.find("worldbody")
    palm = world.find("body")
    palm.set("pos", "0 0 .35")
    return compose_benchmark(root, config)


def compose_benchmark(root, config):
    """Identical object/support/force-pair setup for any prepared hand model."""
    world = root.find("worldbody")
    palm = world.find("body")
    ET.SubElement(world, "light", pos="0 -0.4 .8", dir="0 1 -1")
    ET.SubElement(world, "geom", name="floor", type="plane", size="1 1 .01", pos="0 0 .04", rgba=".25 .28 .3 1")
    cx, cy, cz = config.center
    table_z = cz-config.height/2
    if config.kind == "grasp":
        ET.SubElement(world, "geom", name="table", type="box", size=".012 .012 .01", pos=f"{cx} {cy} {table_z-.01}", friction=".4 .005 .0001", rgba=".55 .4 .25 1")
        obj = ET.SubElement(world, "body", name="target", pos=f"{cx} {cy} {cz}")
        ET.SubElement(obj, "freejoint", name="object_free")
        ET.SubElement(obj, "geom", name="target_geom", type="cylinder", size=f"{config.radius} {config.height/2}", mass=str(config.mass), friction=f"{config.friction} .005 .0001", condim="4", rgba=".85 .38 .12 1")
    elif config.kind == "button":
        # Horizontal spring travel along +Y; gravity cannot activate the button.
        obj = ET.SubElement(world, "body", name="target", pos=f"{cx} {cy} {cz}")
        ET.SubElement(obj, "joint", name="button_slide", type="slide", axis="0 1 0", range="0 .014", stiffness="160", damping="2", armature=".001")
        ET.SubElement(obj, "geom", name="target_geom", type="box", size=".012 .004 .012", mass=str(config.mass), friction=f"{config.friction} .005 .0001", rgba=".2 .7 .3 1")
        ET.SubElement(world, "geom", name="button_housing", type="box", pos=f"{cx} {cy+.04} {cz}", size=".024 .012 .024", rgba=".3 .3 .4 1")
    if config.kind != "empty":
        # Explicit CONTACT-PAIR properties, avoiding MuJoCo's geom max-friction mix.
        contact=root.find("contact")
        for geom in palm.iter("geom"):
            if geom.get("name") and geom.get("contype","1")!="0":
                ET.SubElement(contact,"pair",geom1="target_geom",geom2=geom.get("name"),condim="4",
                              friction=f"{config.friction} {config.friction} .005 .0001 .0001")
        if config.kind=="grasp":
            ET.SubElement(contact,"pair",geom1="target_geom",geom2="table",condim="3",friction=".4 .4 .005 .0001 .0001")
    xml = ET.tostring(root, encoding="unicode")
    return mujoco.MjModel.from_xml_string(xml), xml
