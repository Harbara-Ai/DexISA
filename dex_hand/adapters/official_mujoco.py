"""Official-URDF MuJoCo embodiments using the existing shared physics adapter."""
import hashlib
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np

from dex_hand.core.outcome import AdapterError, FailureClass as F
from dex_hand.sim.worlds import WorldConfig, compose_benchmark
from .mujoco_base import MuJoCoHandAdapter

ROOT = Path(__file__).resolve().parents[2]

READINESS_SOURCES=(
    'dex_hand/adapters/official_mujoco.py','dex_hand/adapters/mujoco_base.py',
    'dex_hand/sim/worlds.py','dex_hand/evaluators/sim_subset.py',
    'dex_hand/modes/maintain_grasp.py','dex_hand/skills/shape_hand.py',
    'dex_hand/skills/make_contact.py','dex_hand/skills/establish_grasp.py',
    'dex_hand/skills/break_contact.py',
    'scripts/build_official_mujoco.py','scripts/run_four_embodiment_physics_smoke.py',
    'assets/embodiment_mujoco/manifest.json','assets/embodiment_audit/sources.json',
    'dex_hand/adapters/profiles/allegro_v5.json',
    'dex_hand/adapters/profiles/robotiq_2f85.json')


def readiness_digest():
    h=hashlib.sha256()
    for name in READINESS_SOURCES:
        h.update(name.encode());h.update((ROOT/name).read_bytes())
    return h.hexdigest()


def _validated_ready(adapter,name):
    path=ROOT/'results_physics_subset/summary.json'
    if not path.exists():return False
    try:
        row=json.loads(path.read_text())
        result=row[name]
        sources=json.loads((ROOT/'assets/embodiment_audit/sources.json').read_text())
        if any(hashlib.sha256((ROOT/item['local_path']).read_bytes()).hexdigest()!=item['sha256']
               for item in sources):return False
        models=json.loads((ROOT/'assets/embodiment_mujoco/manifest.json').read_text())
        model=models[name]
        if hashlib.sha256((ROOT/model['base_xml']).read_bytes()).hexdigest()!=model['sha256']:
            return False
        return (row.get('readiness_digest')==readiness_digest() and
            result['model_sha256']==hashlib.sha256(adapter.xml.encode()).hexdigest() and
            result['same_model'] and result['skill_pass'] and
            all(result['direct_stages'].values()) and
            set(result['direct_stages'])=={
                'SHAPE_HAND','MAKE_CONTACT','ESTABLISH_GRASP','MAINTAIN_GRASP','BREAK_CONTACT'})
    except (KeyError, ValueError, OSError):return False


def _world(name, config, position, quat):
    variable = {'allegro_v5':'ALLEGRO_V5_MJCF', 'robotiq_2f85':'ROBOTIQ_2F85_MJCF'}[name]
    configured = os.environ.get(variable)
    if not configured:
        raise AdapterError(F.NOT_SUPPORTED, f'Set {variable} to an external generated base XML; model and meshes are not bundled')
    path = Path(configured).expanduser()
    if not path.is_file():
        raise AdapterError(F.NOT_SUPPORTED, f'{variable} model missing: {path}')
    path = path.resolve()
    root = ET.parse(path).getroot()
    meshdir = Path(root.find('compiler').get('meshdir', path.parent))
    if not meshdir.is_absolute():
        meshdir = path.parent / meshdir
    for mesh in root.findall('asset/mesh'):
        mesh_path = Path(mesh.get('file', ''))
        if not mesh_path.is_absolute():
            mesh_path = meshdir / mesh_path
        if not mesh_path.is_file():
            raise AdapterError(F.NOT_SUPPORTED, f'{name} mesh missing: {mesh_path}')
        mesh.set('file', mesh_path.resolve().as_posix())
    palm = root.find('worldbody/body')
    palm.set('pos', ' '.join(str(v) for v in position))
    palm.set('quat', ' '.join(str(v) for v in quat))
    return compose_benchmark(root, config)


class AllegroV5MuJoCoAdapter(MuJoCoHandAdapter):
    def __init__(self, config=None):
        config = config or WorldConfig(center=(.08,.068,.30), height=.05, radius=.025, friction=1.2)
        mapping = {'primary':'link_3_0','auxiliary':'link_7_0',
                   'auxiliary_2':'link_11_0','opposition':'link_15_0'}
        super().__init__(config,_world('allegro_v5',config,(0,0,.35),(1,0,0,0)),mapping,
                         {k:'allegro_v5_'+k+'_tip' for k in mapping},
                         'allegro_v5_fixed_palm','Allegro V5 right-B official URDF collision import',
                         'Wonikrobotics-git/allegro_hand_ros2_v5@80bd4a88')
        self.joint_names = tuple(self.model.joint(j).name for j in self.joints)
        # Use the official fake-hardware initial joint vector, not an inferred HOME.
        from .offline_profile import PROFILE_DIR
        import json
        profile=json.loads((PROFILE_DIR/'allegro_v5.json').read_text())
        q=np.array(profile['initial_positions'])
        for index,name in enumerate(self.joint_names):
            self.data.qpos[self.qids[index]]=q[int(name.split('_')[1])]
        self.command_joint_targets(self.get_joint_positions())
        mujoco.mj_forward(self.model,self.data)

    def get_capabilities(self):
        result=super().get_capabilities()
        result.update(backend='MUJOCO_OFFICIAL_URDF', morphology='four_finger_16_dof',
                      benchmark_ready=_validated_ready(self,'allegro_v5'),
                      benchmark_ready_sim=_validated_ready(self,'allegro_v5'),
                      BENCHMARK_READY_SIM=_validated_ready(self,'allegro_v5'),
                      supported_skills=['SHAPE_HAND','MAKE_CONTACT','ESTABLISH_GRASP','BREAK_CONTACT'],
                      supported_modes=['MAINTAIN_GRASP'],
                      force_limits='official URDF effort caps on MuJoCo position actuators')
        return result

    def get_hardware_health(self):
        return {'backend':'MUJOCO','hardware_fault':'UNAVAILABLE',
                'simulation_warnings':sum(w.number for w in self.data.warning)}

    direct_get_state = MuJoCoHandAdapter.build_canonical_observation
    direct_set_joint_targets = MuJoCoHandAdapter.command_joint_targets
    direct_stop = MuJoCoHandAdapter.safe_hold


class Robotiq2F85MuJoCoAdapter(MuJoCoHandAdapter):
    def __init__(self, config=None):
        config = config or WorldConfig(center=(0,0,.22),radius=.015,friction=1.2)
        mapping={'primary':'robotiq_85_left_finger_tip_link',
                 'opposition':'robotiq_85_right_finger_tip_link'}
        super().__init__(config,_world('robotiq_2f85',config,(0,0,.35),(0,1,0,0)),mapping,
                         {k:'robotiq_2f85_'+k+'_tip' for k in mapping},
                         'robotiq_2f85_fixed_palm','Robotiq 2F-85 official URDF collision import',
                         'robotiq/ros@8d7b8412ad685ffe1db5719da6e8fce6c1896e5e')
        self._desired_gap=None
        self._gap_direction=1
        self.command_joint_targets([0.0])
        mujoco.mj_forward(self.model,self.data)

    def get_capabilities(self):
        result=super().get_capabilities()
        result.update(backend='MUJOCO_OFFICIAL_URDF',
                      morphology='one_active_joint_five_mimic_constraints',
                      benchmark_ready=_validated_ready(self,'robotiq_2f85'),
                      benchmark_ready_sim=_validated_ready(self,'robotiq_2f85'),
                      BENCHMARK_READY_SIM=_validated_ready(self,'robotiq_2f85'),
                      supported_skills=['SHAPE_HAND','MAKE_CONTACT','ESTABLISH_GRASP','BREAK_CONTACT'],
                      supported_modes=['MAINTAIN_GRASP'], force_limits='official URDF single joint effort cap',
                      coupled_contact_groups=True)
        return result

    def get_hardware_health(self):
        return {'backend':'MUJOCO','hardware_fault':'UNAVAILABLE',
                'simulation_warnings':sum(w.number for w in self.data.warning)}

    def _project_mimics(self, data, active):
        data.qpos[self.qids[0]]=active
        for name,mult in (('robotiq_85_right_knuckle_joint',-1),
                          ('robotiq_85_left_inner_knuckle_joint',1),
                          ('robotiq_85_right_inner_knuckle_joint',-1),
                          ('robotiq_85_left_finger_tip_joint',-1),
                          ('robotiq_85_right_finger_tip_joint',1)):
            j=self.model.joint(name).id
            data.qpos[self.model.jnt_qposadr[j]]=active*mult
        mujoco.mj_forward(self.model,data)

    def _gap(self, value):
        self.ik_data.qpos[:]=self.data.qpos
        self._project_mimics(self.ik_data,value)
        return float(np.linalg.norm(self.ik_data.site_xpos[self.sites['primary']]-
                                    self.ik_data.site_xpos[self.sites['opposition']]))

    def _position_for_gap(self, gap):
        lo,hi=map(float,self.limits[0]);glo,ghi=self._gap(lo),self._gap(hi)
        if not min(glo,ghi)-1e-7<=gap<=max(glo,ghi)+1e-7:
            raise AdapterError(F.UNREACHABLE,'requested aperture outside source-defined coupled travel')
        for _ in range(35):
            mid=(lo+hi)/2;gm=self._gap(mid)
            if (gm-gap)*(glo-gap)>0:lo,glo=mid,gm
            else:hi=mid
        return [(lo+hi)/2]

    def prepare_configuration(self, profile, object_id, groups, aperture=.06, clearance=.008):
        if profile not in ('PRESHAPE','POSTURE','POINT','OPEN','CLOSED','INTERMEDIATE'):
            raise AdapterError(F.NOT_SUPPORTED,'unsupported shared profile')
        if object_id!='target' or self.object_id is None:
            raise AdapterError(F.PRECONDITION_FAILED,'object absent')
        if not groups or {g.group_id for g in groups}-set(self.sites):
            raise AdapterError(F.NOT_SUPPORTED,'unknown coupled contact group')
        if not .02<=aperture<=.12 or clearance<0:
            raise AdapterError(F.UNREACHABLE,'aperture outside benchmark envelope')
        lo,hi=map(float,self.limits[0]);gaps=(self._gap(lo),self._gap(hi))
        self._desired_gap=({'OPEN':max(gaps),'CLOSED':min(gaps),
            'INTERMEDIATE':sum(gaps)/2}.get(profile,aperture+2*clearance))
        self.group_targets={g.group_id:self._desired_gap for g in groups}
        self.command_joint_targets(self._position_for_gap(self._desired_gap))

    def configuration_error(self):
        return 0. if self._desired_gap is None else abs(self._gap(float(self.get_joint_positions()[0]))-
                                                     self._desired_gap)/2

    def advance_groups(self, object_id, groups, distances):
        if object_id!='target' or self._desired_gap is None:
            raise AdapterError(F.PRECONDITION_FAILED,'preshape required')
        if len(groups)!=len(distances) or not groups:
            raise AdapterError(F.PRECONDITION_FAILED,'group displacement mismatch')
        if {g.group_id for g in groups}-set(self.group_targets):
            raise AdapterError(F.PRECONDITION_FAILED,'unprepared group')
        # One actuator: requested per-side travel maps to a single jaw gap.
        distance=float(np.mean(distances))
        self._desired_gap-=2*distance
        self.command_joint_targets(self._position_for_gap(self._desired_gap))

    def set_gripper_target(self, position_rad):
        return self.command_joint_targets([position_rad])

    direct_get_state = MuJoCoHandAdapter.build_canonical_observation
    direct_stop = MuJoCoHandAdapter.safe_hold
