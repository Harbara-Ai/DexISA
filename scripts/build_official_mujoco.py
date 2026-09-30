"""Deterministically import pinned vendor URDFs into fixed-palm MuJoCo bases."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
import mujoco

AUDIT = Path(os.environ.get('DEXISA_VENDOR_ASSET_ROOT', ROOT / 'assets/embodiment_audit')).expanduser().resolve()
OUT = Path(os.environ.get('DEXISA_GENERATED_MODEL_DIR', ROOT / 'assets/embodiment_mujoco')).expanduser().resolve()


def import_urdf(source, output):
    model = mujoco.MjModel.from_xml_string(source)
    mujoco.mj_saveLastXML(str(output), model)
    return ET.parse(output).getroot()


def build_allegro():
    path = AUDIT / 'Wonikrobotics-git_allegro_hand_ros2_v5/src/allegro_hand_controllers/urdf/allegro_hand_description_right_B.urdf'
    source = path.read_text().replace('package://allegro_hand_controllers/', path.parent.parent.resolve().as_posix()+'/')
    root = import_urdf(source, OUT/'allegro_import.xml')
    return root, 'allegro_v5', [f'joint_{i}_0' for i in range(16)],


def build_robotiq():
    path = AUDIT / 'robotiq_ros/grippers/robotiq_description/urdf/robotiq_2f_85_macro.urdf.xacro'
    macro = ET.parse(path).getroot().find('{http://wiki.ros.org/xacro}macro')
    urdf = ET.Element('robot', name='robotiq_2f85')
    ET.SubElement(urdf, 'link', name='world')
    for element in macro:
        if element.tag not in ('link', 'joint'):
            continue
        element = copy.deepcopy(element)
        for node in element.iter():
            for key, value in list(node.attrib.items()):
                value = value.replace('${prefix}', '').replace('${parent}', 'world')
                if key == 'filename' and value.startswith('package://robotiq_description/'):
                    value = (path.parent.parent / value.removeprefix('package://robotiq_description/')).resolve().as_posix()
                node.set(key, value)
            for child in list(node):
                if child.tag == 'visual' or child.tag.startswith('{'):
                    node.remove(child)
        urdf.append(element)
    root = import_urdf(ET.tostring(urdf, encoding='unicode'), OUT/'robotiq_import.xml')
    return root, 'robotiq_2f85', ['robotiq_85_left_knuckle_joint'],


def finalize(root, name, actuated):
    profile = json.loads((ROOT/'dex_hand/adapters/profiles'/(name+'.json')).read_text())
    world = root.find('worldbody')
    palm = ET.Element('body', name=name+'_fixed_palm')
    for child in list(world):
        world.remove(child)
        palm.append(child)
    world.append(palm)
    for index, geom in enumerate(palm.iter('geom')):
        geom.set('name', name+'_collision_'+str(index))
    option = root.find('option')
    if option is None:
        option = ET.SubElement(root, 'option')
    option.set('timestep', '.002')
    option.set('integrator', 'implicitfast')
    option.set('gravity', '0 0 -9.81')
    option.set('iterations', '80')
    if root.find('contact') is None:
        ET.SubElement(root, 'contact')
    actuator = root.find('actuator')
    if actuator is None:
        actuator = ET.SubElement(root, 'actuator')
    for joint in profile['joint_definitions']:
        if joint['name'] in actuated:
            ET.SubElement(actuator, 'position', name=joint['name']+'_position',
                joint=joint['name'], kp='10' if name=='robotiq_2f85' else '50',
                kv='1' if name=='robotiq_2f85' else '2',
                forcelimited='true', forcerange=f"{-joint['effort']} {joint['effort']}")
    if name=='robotiq_2f85':
        # Source xacro has inertias and mimic relations but no joint damping
        # or motor dynamics. These are explicit MuJoCo numerical regularizers,
        # not vendor performance or real-hardware limits.
        for joint in palm.iter('joint'):
            joint.set('damping','.1')
            joint.set('armature','.001')
    # Sites come from source link frames or fixed-tip joints. They are not
    # collision geometry and never enter a contact/force computation.
    if name == 'allegro_v5':
        urdf = ET.parse(AUDIT/'Wonikrobotics-git_allegro_hand_ros2_v5/src/allegro_hand_controllers/urdf/allegro_hand_description_right_B.urdf').getroot()
        for i, label in ((3,'primary'),(7,'auxiliary'),(11,'auxiliary_2'),(15,'opposition')):
            joint = next(j for j in urdf.findall('joint') if j.get('name') == f'joint_{i}_0_tip')
            xyz = joint.find('origin').get('xyz')
            body = palm.find(f".//body[@name='link_{i}_0']")
            ET.SubElement(body, 'site', name=name+'_'+label+'_tip', pos=xyz, size='.002')
    else:
        for label, side in (('primary','left'),('opposition','right')):
            body = palm.find(f".//body[@name='robotiq_85_{side}_finger_tip_link']")
            ET.SubElement(body, 'site', name=name+'_'+label+'_tip', size='.002')
    target = OUT/(name+'_base.xml')
    target.write_text(ET.tostring(root, encoding='unicode'), encoding='utf-8')
    model = mujoco.MjModel.from_xml_path(str(target))
    data = mujoco.MjData(model)
    if name == 'allegro_v5':
        for j, q in zip(profile['joint_definitions'], profile['initial_positions']):
            jid=model.joint(j['name']).id
            data.qpos[model.jnt_qposadr[jid]]=q
    mujoco.mj_forward(model,data)
    # Imported collision meshes include overlapping attached shells at the
    # official initial configuration. Exclude those exact body pairs, while
    # retaining all other hand-hand and every hand-object collision.
    excluded=set()
    for contact in data.contact[:data.ncon]:
        if contact.dist >= 0:
            continue
        b1,b2=(int(model.geom_bodyid[int(g)]) for g in (contact.geom1, contact.geom2))
        if b1 and b2 and b1!=b2:
            excluded.add(tuple(sorted((model.body(b1).name,model.body(b2).name))))
    for b1,b2 in sorted(excluded):
        ET.SubElement(root.find('contact'),'exclude',body1=b1,body2=b2)
    target.write_text(ET.tostring(root, encoding='unicode'), encoding='utf-8')
    model = mujoco.MjModel.from_xml_path(str(target))
    assert model.nu == len(actuated)
    assert model.nmesh > 0
    assert model.neq == (5 if name=='robotiq_2f85' else 0)
    return {'base_xml': str(target.relative_to(ROOT)).replace('\\','/'),
            'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'nq':model.nq,'nu':model.nu,'ngeom':model.ngeom,'nmesh':model.nmesh,'neq':model.neq,
            'initial_interpenetrating_body_pairs_excluded':len(excluded),
            'excluded_pairs':[list(pair) for pair in sorted(excluded)]}


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    entries = {}
    for builder in (build_allegro, build_robotiq):
        root, name, joints = builder()
        entries[name] = finalize(root, name, joints)
    (OUT/'manifest.json').write_text(json.dumps(entries, indent=2))
    print(json.dumps(entries, indent=2))
