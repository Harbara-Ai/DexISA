"""Shared MuJoCo adapter mechanics and estimator, parameterized by embodiment."""
import numpy as np
import mujoco
from dex_hand.core.observation import *
from dex_hand.core.capability import mujoco_capabilities
from dex_hand.core.outcome import AdapterError, FailureClass as F


class MuJoCoHandAdapter:
    def __init__(self, config, built_world, group_map, site_names, palm_name, model_name, source):
        self.config = config
        self.model, self.xml = built_world
        self.model_name, self.source = model_name, source
        self.data = mujoco.MjData(self.model)
        self.ik_data = mujoco.MjData(self.model)
        self.dt = self.model.opt.timestep
        self.callbacks = []
        self.active_modes = []
        self.events = []
        self.last_command = {}
        self.phase = "IDLE"
        self.skill = "IDLE"
        self.grasp_verified = False
        self.verified_groups = ()
        self.verified_reference = None
        self.group_map = group_map
        self.sites = {k: self.model.site(v).id for k, v in site_names.items()}
        self.joints = self.model.actuator_trnid[:, 0].copy()
        self.qids = self.model.jnt_qposadr[self.joints]
        self.dofs = self.model.jnt_dofadr[self.joints]
        self.limits = self.model.jnt_range[self.joints].copy()
        self.target = self.data.qpos[self.qids].copy()
        self.group_targets = {}
        self.group_directions = {}
        self.palm_id = self.model.body(palm_name).id
        self.object_id = self.model.body("target").id if config.kind != "empty" else None
        self.object_geom = self.model.geom("target_geom").id if self.object_id else None
        self.geom_groups = {}
        for i in range(self.model.ngeom):
            body_name = self.model.body(self.model.geom_bodyid[i]).name
            self.geom_groups[i] = next((k for k, prefix in self.group_map.items() if body_name.startswith(prefix)), "other")
        mujoco.mj_forward(self.model, self.data)

    def get_capabilities(self):
        return {"available": True, "observation_profile": "MUJOCO_NO_TACTILE",
                "supported_skills": ["SHAPE_HAND", "MAKE_CONTACT", "ESTABLISH_GRASP", "BREAK_CONTACT", "APPLY_WRENCH"],
                "supported_modes": ["MAINTAIN_GRASP"], "grasp_evaluator": "BASELINE_STATIC_V1",
                "task_wrench_feasibility": False, "aperture_range_m": [.02, .12],
                "point_posture": True, "force_limits": "original MJCF, unchanged",
                "model": self.model_name, "source": self.source}

    def get_observation_capabilities(self):
        return mujoco_capabilities(1/self.dt)

    def read_raw_state(self):
        return {"qpos": self.data.qpos.copy(), "qvel": self.data.qvel.copy(), "effort": self.data.qfrc_actuator.copy(), "timestamp": self.data.time}

    def get_joint_positions(self): return self.data.qpos[self.qids].copy()
    def get_joint_velocities(self): return self.data.qvel[self.dofs].copy()
    def get_joint_efforts(self): return self.data.qfrc_actuator[self.dofs].copy()

    def command_actuators(self, command):
        command = np.asarray(command, dtype=float)
        if command.shape != (self.model.nu,) or not np.isfinite(command).all():
            raise AdapterError(F.PRECONDITION_FAILED, "invalid actuator command")
        if np.any(command < self.limits[:, 0]) or np.any(command > self.limits[:, 1]):
            raise AdapterError(F.ACTUATOR_LIMIT, "target exceeds joint range")
        self.target = command.copy()
        self.data.ctrl[:] = command
        self.last_command = {"kind": "position_servo", "targets": command.tolist()}

    command_joint_positions = command_actuators
    command_joint_targets = command_actuators

    def get_contact_groups(self): return tuple(self.group_map)

    def resolve_contact_group(self, group):
        name = group.group_id if hasattr(group, "group_id") else group
        if name not in self.sites:
            raise AdapterError(F.NOT_SUPPORTED, f"unknown virtual contact group {name}")
        return self.sites[name]

    def get_contact_group_pose(self, group):
        site = self.resolve_contact_group(group)
        quat = np.empty(4)
        mujoco.mju_mat2Quat(quat, self.data.site_xmat[site])
        return Pose("world", self.data.site_xpos[site].tolist(), quat.tolist())

    def _ik(self, targets, iterations=120):
        d, m = self.ik_data, self.model
        d.qpos[:] = self.data.qpos
        d.qpos[self.qids] = self.target
        for _ in range(iterations):
            mujoco.mj_forward(m, d)
            errors, jacobians = [], []
            for name, point in targets.items():
                site = self.sites[name]
                jac = np.zeros((3, m.nv))
                mujoco.mj_jacSite(m, d, jac, None, site)
                errors.extend(point-d.site_xpos[site])
                jacobians.append(jac[:, self.dofs])
            err, jac = np.array(errors), np.vstack(jacobians)
            if np.linalg.norm(err, ord=np.inf) < .00001: break
            delta = jac.T @ np.linalg.solve(jac @ jac.T + np.eye(len(err))*1e-5, err)
            delta *= min(1., .12/max(np.max(np.abs(delta)), 1e-12))
            d.qpos[self.qids] = np.clip(d.qpos[self.qids]+delta, self.limits[:, 0], self.limits[:, 1])
        mujoco.mj_forward(m, d)
        residual = max(np.linalg.norm(point-d.site_xpos[self.sites[name]]) for name, point in targets.items())
        return d.qpos[self.qids].copy(), residual

    def prepare_configuration(self, profile, object_id, groups, aperture=.06, clearance=.008):
        if profile not in ("PRESHAPE", "POSTURE", "POINT"):
            raise AdapterError(F.NOT_SUPPORTED, f"unsupported profile {profile}")
        if object_id != "target" or self.object_id is None:
            raise AdapterError(F.PRECONDITION_FAILED, "object not present")
        if not .02 <= aperture <= .12:
            raise AdapterError(F.UNREACHABLE, "aperture outside capability")
        points, directions = {}, {}
        center = self.data.xpos[self.object_id].copy()
        rotation = self.data.xmat[self.object_id].reshape(3, 3)
        for group in groups:
            self.resolve_contact_group(group)
            if group.frame != "object":
                raise AdapterError(F.NOT_SUPPORTED, "this realization supports object-frame regions only")
            normal = np.asarray(group.outward, dtype=float)
            if np.linalg.norm(normal) < .99 or abs(np.linalg.norm(normal)-1) > .01:
                raise AdapterError(F.PRECONDITION_FAILED, "surface direction must be a unit vector")
            normal = rotation @ normal
            radius = .004 if self.config.kind == "button" else aperture/2
            points[group.group_id] = center + normal*(radius+clearance)
            directions[group.group_id] = -normal
        q, residual = self._ik(points)
        if residual > .003:
            raise AdapterError(F.UNREACHABLE, f"contact-group IK residual {residual:.5f} m")
        self.group_targets, self.group_directions = points, directions
        self.command_joint_targets(q)

    def configuration_error(self):
        return max((np.linalg.norm(point-self.data.site_xpos[self.sites[name]]) for name, point in self.group_targets.items()), default=0.)

    def advance_groups(self, object_id, groups, distances):
        if object_id != "target": raise AdapterError(F.PRECONDITION_FAILED, "unknown object")
        points = {k: v.copy() for k, v in self.group_targets.items()}
        for g, distance in zip(groups, distances):
            if g.group_id not in points:
                raise AdapterError(F.PRECONDITION_FAILED, "contact group has no prepared approach")
            points[g.group_id] += self.group_directions[g.group_id]*float(distance)
        q, error = self._ik(points, 12)
        if error > .005: raise AdapterError(F.UNREACHABLE, f"incremental IK residual {error:.5f} m")
        self.group_targets = points
        self.command_joint_targets(q)

    def safe_hold(self):
        self.command_joint_targets(np.clip(self.get_joint_positions(), self.limits[:, 0], self.limits[:, 1]))
        self.last_command["safe_state"]="STOP_MOTION_HOLD_MEASURED_POSTURE_WITH_ORIGINAL_FORCE_CAPS"

    def add_step_callback(self, callback):
        if callback not in self.callbacks: self.callbacks.append(callback)

    def remove_step_callback(self, callback):
        if callback in self.callbacks: self.callbacks.remove(callback)

    def step(self, steps=1):
        for _ in range(steps):
            mujoco.mj_step(self.model, self.data)
            # Refresh all derived quantities at the same post-step timestamp.
            mujoco.mj_forward(self.model, self.data)
            if not np.isfinite(self.data.qpos).all(): raise RuntimeError("nonfinite simulation state")
            for callback in tuple(self.callbacks): callback(self.build_canonical_observation())

    def build_canonical_observation(self):
        d, m, t = self.data, self.model, float(self.data.time)
        contacts, wrench = [], np.zeros(6)
        collision, supported = False, self.config.kind == "button"
        for i in range(d.ncon):
            c = d.contact[i]
            g1, g2 = int(c.geom1), int(c.geom2)
            rawforce = np.zeros(6)
            mujoco.mj_contactForce(m, d, i, rawforce)
            if rawforce[0] < 1e-5: continue
            if self.object_geom not in (g1, g2):
                if m.geom_bodyid[g1] != 0 or m.geom_bodyid[g2] != 0: collision = True
                continue
            other = g2 if g1 == self.object_geom else g1
            if m.geom_bodyid[other] == 0:
                supported = True
                continue
            group = self.geom_groups[other]
            sign = 1. if g2 == self.object_geom else -1.
            frame = c.frame.reshape(3, 3)
            force = sign * (frame.T @ rawforce[:3])
            normal = sign * frame[0]
            wrench[:3] += force
            wrench[3:] += np.cross(c.pos-d.xpos[self.object_id], force)+sign*(frame.T@rawforce[3:])
            src = "SIM_CONTACT"
            contacts.append(ContactObservation(f"contact:{other}:{i}", group, "target", known(True,t,src),
                known({"frame":"world", "xyz":c.pos.tolist()},t,src), known({"frame":"world", "xyz":normal.tolist()},t,src),
                known(float(rawforce[0]),t,src), known({"frame":"world", "xyz":(force-normal*rawforce[0]).tolist()},t,src,Method.DERIVED), unknown(t)))
        objects = {}
        if self.object_id:
            bid = self.object_id
            vel = np.zeros(6)
            mujoco.mj_objectVelocity(m,d,mujoco.mjtObj.mjOBJ_BODY,bid,vel,0)
            R = d.xmat[self.palm_id].reshape(3,3)
            relative = R.T @ (d.xpos[bid]-d.xpos[self.palm_id])
            relative_quat = np.empty(4)
            mujoco.mju_mat2Quat(relative_quat, (R.T @ d.xmat[bid].reshape(3,3)).ravel())
            displacement = float(d.qpos[m.jnt_qposadr[m.joint("button_slide").id]]) if self.config.kind == "button" else None
            objects["target"] = ObjectObservation(known(Pose("world",d.xpos[bid].tolist(),d.xquat[bid].tolist()),t),
                known({"frame":"world", "angular":vel[:3].tolist(),"linear":vel[3:].tolist()},t),
                known(Pose("palm",relative.tolist(),relative_quat.tolist()),t,method=Method.DERIVED),
                known({"frame":"palm", "angular":(R.T@vel[:3]).tolist(),"linear":(R.T@vel[3:]).tolist()},t,method=Method.DERIVED),
                known(displacement,t) if displacement is not None else unknown(t, unavailable=True),
                known(displacement >= .008,t,method=Method.DERIVED) if displacement is not None else unknown(t,unavailable=True),
                known(supported,t,"SIM_CONTACT",Method.DERIVED))
        loads = {g: sum(c.normal_load.value for c in contacts if c.contact_group_id == g) for g in self.verified_groups}
        stationary = (bool(objects) and np.linalg.norm(objects["target"].relative_velocity.value["linear"]) < .015
                      and np.linalg.norm(objects["target"].relative_velocity.value["angular"]) < .5)
        within_reference = (self.verified_reference is not None and bool(objects)
                            and np.linalg.norm(np.array(objects["target"].relative_pose.value.position)-self.verified_reference)<.008)
        stable = self.grasp_verified and bool(loads) and min(loads.values()) >= .15 and stationary and within_reference
        grasp = "STABLE" if stable else "MARGINAL" if contacts else "UNSTABLE"
        saturated = np.any(np.abs(d.actuator_force) >= .98*np.max(np.abs(m.actuator_forcerange),axis=1))
        hand = HandObservation(known(self.get_joint_positions().tolist(),t),known(self.get_joint_velocities().tolist(),t),
            known(self.get_joint_efforts().tolist(),t),known(bool(saturated),t,method=Method.DERIVED),known(collision,t,"SIM_CONTACT",Method.DERIVED))
        return CanonicalObservation(t,hand,contacts,objects,
            InteractionObservation(unknown(t),known({"frame":"world","about":"object_com","force":wrench[:3].tolist(),"torque":wrench[3:].tolist()},t,"SIM_CONTACT",Method.DERIVED)),
            GraspObservation(known(grasp,t,"BASELINE_STATIC_V1",Method.ESTIMATED,.6),unknown(t)),list(self.active_modes))
