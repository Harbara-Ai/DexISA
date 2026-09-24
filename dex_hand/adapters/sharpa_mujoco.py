"""Official Sharpa Wave mapping; no hand-specific task sequence."""
from pathlib import Path
import os
import xml.etree.ElementTree as ET
import numpy as np
import mujoco
from .mujoco_base import MuJoCoHandAdapter
from dex_hand.core.outcome import AdapterError, FailureClass as F
from dex_hand.sim.worlds import WorldConfig, compose_benchmark


def find_sharpa_asset():
    configured=os.environ.get("SHARPA_MJCF")
    if not configured:
        raise AdapterError(F.NOT_SUPPORTED,"Set SHARPA_MJCF to the external Sharpa Wave XML; XML, matching URDF and meshes are not bundled")
    path=Path(configured).expanduser()
    if not path.is_file() or not path.with_suffix(".urdf").is_file():
        raise AdapterError(F.NOT_SUPPORTED,f"Sharpa XML or matching URDF missing: {path}")
    return path.resolve()


SHARPA_MOUNT = (-.04, .02, .36)


def build_sharpa_world(config, asset=None, mount_pos=SHARPA_MOUNT):
    asset=Path(asset or find_sharpa_asset())
    root=ET.parse(asset).getroot()
    urdf=ET.parse(asset.with_suffix(".urdf")).getroot()
    meshdir=(asset.parent/"meshes").resolve()
    for mesh in root.findall("asset/mesh"):
        mesh_path=meshdir/mesh.get("file", "")
        if not mesh_path.is_file():
            raise AdapterError(F.NOT_SUPPORTED,f"Sharpa mesh missing: {mesh_path}")
    root.find("compiler").set("meshdir",str(meshdir))
    ET.SubElement(root,"option",timestep=str(config.timestep),integrator="implicitfast",gravity="0 0 -9.81",iterations="80")
    joints={j.get("name"):j for j in urdf.findall("joint")}
    # Source XML omits effort caps. Populate them from SAME official URDF.
    for actuator in root.find("actuator"):
        limit=float(joints[actuator.get("joint")].find("limit").get("effort"))
        actuator.set("forcerange",f"{-limit} {limit}")
    palm=root.find("worldbody/body")
    palm.set("pos"," ".join(map(str,mount_pos)))
    # Native +Z fingers -> world -Z; native palm normal +X -> world +Y.
    palm.set("quat","0 .7071067811865476 .7071067811865476 0")
    for finger in ("thumb","index","middle","ring","pinky"):
        body=palm.find(f".//body[@name='right_{finger}_DP']")
        elastomer=body.find(f"geom[@name='right_{finger}_elastomer']")
        joint=joints[f"right_{finger}_fingertip_fix_joint"]
        offset=np.fromstring(joint.find("origin").get("xyz"),sep=" ")
        rotation=np.empty(9)
        mujoco.mju_quat2Mat(rotation,np.fromstring(elastomer.get("quat"),sep=" "))
        point=rotation.reshape(3,3)@offset
        ET.SubElement(body,"site",name=f"right_{finger}_fingertip",pos=" ".join(map(str,point)),size=".002",group="4")
    for i,geom in enumerate(palm.iter("geom")):
        if geom.get("name") is None:geom.set("name",f"sharpa_geom_{i}")
    return compose_benchmark(root,config)


class SharpaMuJoCoAdapter(MuJoCoHandAdapter):
    def __init__(self, config=WorldConfig(), asset=None, mount_pos=SHARPA_MOUNT):
        mapping={"opposition":"right_thumb","primary":"right_index","auxiliary":"right_middle"}
        super().__init__(config,build_sharpa_world(config,asset,mount_pos),mapping,
                         {k:v+"_fingertip" for k,v in mapping.items()},"right_hand_C_MC",
                         "Sharpa Wave right (official)",str(asset or find_sharpa_asset()))
        # Collision-clear rest posture of nonparticipating digits, independent
        # of object size/material. This is an initial hand configuration, not
        # a task trajectory or a reset of object/contact state.
        for i,jid in enumerate(self.joints):
            name=self.model.joint(jid).name
            if any(name.startswith(f"right_{f}_") for f in ("middle","ring","pinky")):
                value=1.4 if name.endswith("MCP_FE") else .3 if name.endswith("MCP_AA") else 0.
                self.data.qpos[self.qids[i]]=value
        self.command_joint_targets(self.get_joint_positions())
        mujoco.mj_forward(self.model,self.data)

    def get_capabilities(self):
        result=super().get_capabilities()
        result["force_limits"]="official matching URDF effort caps; XML source omitted caps"
        return result
