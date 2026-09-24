"""Source-pinned, device-free state and command adapter for conformance work.

This is a joint-state mock, not an object/contact or force simulator. It does not
import vendor drivers, open ports, run ROS, or claim physical task completion.
"""
from copy import deepcopy
import json
import math
from pathlib import Path

from dex_hand.core.capability import Availability, OBSERVABLES, ObservationCapability
from dex_hand.core.observation import (CanonicalObservation, GraspObservation,
    HandObservation, InteractionObservation, Method, ObservedValue, ValueStatus,
    known, unknown)
from dex_hand.core.outcome import AdapterError, FailureClass as F, SkillOutcome


PROFILE_DIR = Path(__file__).with_name('profiles')


def _vector(values, size, *, label):
    if not isinstance(values, (list, tuple)) or len(values) != size:
        raise AdapterError(F.PRECONDITION_FAILED, f'{label} needs {size} values')
    try:
        values = tuple(float(v) for v in values)
    except (TypeError, ValueError) as exc:
        raise AdapterError(F.PRECONDITION_FAILED, f'{label} must be numeric') from exc
    if not all(math.isfinite(v) for v in values):
        raise AdapterError(F.PRECONDITION_FAILED, f'{label} must be finite')
    return values


class OfflineProfileAdapter:
    """Common HandAdapter mechanics; morphology stays in each pinned profile."""

    profile_name = None

    def __init__(self):
        self.profile = json.loads((PROFILE_DIR / (self.profile_name+'.json')).read_text())
        self.joints = tuple(j['name'] for j in self.profile['joint_definitions'])
        self._q = tuple(self.profile['initial_positions'])
        self._target = self._q
        self._q_provenance = 'OFFLINE_MOCK_STATE'
        self._velocity = None
        self._velocity_provenance = 'NO_MOCK_VELOCITY_MODEL'
        self._effort = None
        self._effort_provenance = 'NO_MEASURED_JOINT_TORQUE'
        self._diagnostics = {}
        self._fault = None
        self._fault_known = False
        self._tick = 0
        self.dt = 1.0  # One logical mock transition, not physical seconds.
        self.active_modes, self.events, self.last_command = [], [], {}
        self.skill, self.phase = 'IDLE', 'IDLE'
        self.grasp_verified, self.verified_groups, self.verified_reference = False, (), None
        self._callbacks = []

    def get_capabilities(self):
        result = {'available': True, 'backend': 'OFFLINE_JOINT_STATE_MOCK',
            'benchmark_ready': True, 'benchmark_scope': 'COMMAND_OBSERVATION_CONFORMANCE_ONLY',
            'model': self.profile['model'], 'morphology': self.profile['morphology'],
            'joint_names': list(self.joints), 'joint_definitions': deepcopy(self.profile['joint_definitions']),
            'source_files': deepcopy(self.profile['sources']),
            'semantic_postures': list(self.profile['postures']),
            'skill_status': deepcopy(self.skill_status()),
            'contact_group_map': deepcopy(self.profile['contact_groups'])}
        if 'coupled_contact_groups' in self.profile:
            result['coupled_contact_groups'] = self.profile['coupled_contact_groups']
        return result

    def skill_status(self):
        raise NotImplementedError

    def get_observation_capabilities(self):
        result = {name: ObservationCapability(Availability.UNAVAILABLE,
                 Method.ESTIMATED, 0, 0, ('NOT_SENSED_IN_JOINT_MOCK',)) for name in OBSERVABLES}
        result['joint_position'] = ObservationCapability(Availability.ALWAYS,
            Method.DIRECT, 0, 0, (self._q_provenance,))
        if self._velocity is not None:
            result['joint_velocity'] = ObservationCapability(Availability.CONDITIONAL,
                Method.DIRECT, 0, 0, (self._velocity_provenance,))
        # Vendor effort/current is diagnostic, not measured joint torque.
        return result

    def read_raw_state(self):
        return {'joint_names': list(self.joints), 'position_rad': list(self._q),
            'velocity_rad_s': None if self._velocity is None else list(self._velocity),
            'target_rad': list(self._target), 'diagnostics': deepcopy(self._diagnostics),
            'fault': deepcopy(self._fault), 'timestamp_tick': self._tick,
            'source': self._q_provenance}

    def get_hardware_health(self):
        return {'backend': 'OFFLINE_ONLY', 'fault': deepcopy(self._fault),
                'fault_availability': 'VALID' if self._fault_known else 'UNAVAILABLE',
                'diagnostics': deepcopy(self._diagnostics),
                'activation': 'UNAVAILABLE', 'provenance': self._q_provenance}

    def build_canonical_observation(self):
        t = float(self._tick)
        q = known(list(self._q), t, self._q_provenance)
        dq = (known(list(self._velocity), t, self._velocity_provenance)
              if self._velocity is not None else unknown(t, self._velocity_provenance, unavailable=True))
        missing = lambda: unknown(t, 'NOT_SENSED_IN_JOINT_MOCK', unavailable=True)
        # No object pose, contact patch, load, collision or wrench is fabricated.
        return CanonicalObservation(t,
            HandObservation(q, dq, missing(), missing(), missing()),
            [], {}, InteractionObservation(missing(), missing()),
            GraspObservation(missing(), missing()), list(self.active_modes))

    def get_joint_positions(self): return list(self._q)
    def get_joint_velocities(self): return None if self._velocity is None else list(self._velocity)
    def get_joint_efforts(self): return None  # Never return motor current or desired torque as effort.

    def _validate_target(self, values):
        values = _vector(values, len(self.joints), label='joint target')
        for j, q in zip(self.profile['joint_definitions'], values):
            if not j['lower'] <= q <= j['upper']:
                raise AdapterError(F.ACTUATOR_LIMIT, f"{j['name']} outside official URDF range")
        return values

    def command_joint_targets(self, targets):
        values = self._validate_target(targets)
        if self._fault is not None:
            raise AdapterError(F.ACTUATOR_LIMIT, 'offline fault latched; clear test fixture first')
        self._target = values
        self.last_command = {'kind': 'joint_position', 'targets_rad': list(values),
                             'source': 'OFFLINE_MOCK_COMMAND'}
        return deepcopy(self.last_command)

    command_joint_positions = command_joint_targets
    command_actuators = command_joint_targets

    def direct_get_state(self):
        return self.build_canonical_observation()

    def direct_set_joint_targets(self, targets):
        return self.command_joint_targets(targets)

    def direct_stop(self):
        return self.safe_hold()

    def safe_hold(self):
        self._target = self._q
        self.last_command = {'kind': 'hold_measured_mock_pose', 'targets_rad': list(self._q)}
        return deepcopy(self.last_command)

    def load_mock_feedback(self, positions, *, velocity=None, diagnostics=None,
                           fault=None, fault_known=False):
        """Inject an offline snapshot; both direct and skill views use this state."""
        self._q = _vector(positions, len(self.joints), label='feedback')
        self._velocity = None if velocity is None else _vector(velocity, len(self.joints), label='velocity')
        self._velocity_provenance = 'OFFLINE_INJECTED_VELOCITY' if velocity is not None else 'NO_MOCK_VELOCITY_MODEL'
        self._q_provenance = 'OFFLINE_INJECTED_JOINT_STATE'
        self._diagnostics = dict(diagnostics or {})
        self._fault = fault
        self._fault_known = bool(fault_known)
        self._tick += 1

    def step(self, steps=1):
        if not isinstance(steps, int) or steps < 0:
            raise AdapterError(F.PRECONDITION_FAILED, 'logical step count must be nonnegative integer')
        for _ in range(steps):
            self._q = self._target
            # This ideal fake-hardware position follower does not model velocity.
            self._velocity = None
            self._velocity_provenance = 'NO_MOCK_VELOCITY_MODEL'
            self._q_provenance = 'OFFLINE_MOCK_STATE'
            self._tick += 1
            observation = self.build_canonical_observation()
            for callback in tuple(self._callbacks):
                callback(observation)

    def add_step_callback(self, callback): self._callbacks.append(callback)
    def remove_step_callback(self, callback): self._callbacks.remove(callback)
    def get_contact_groups(self): return tuple(self.profile['contact_groups'])

    def _no_contact_model(self, *args, **kwargs):
        raise AdapterError(F.NOT_SUPPORTED, 'joint mock has no object/contact physics or load sensing')

    resolve_contact_group = get_contact_group_pose = prepare_configuration = _no_contact_model
    configuration_error = advance_groups = _no_contact_model

    def execute_posture(self, semantic, *, abort_on_contact=True, **kwargs):
        if semantic not in self.profile['postures']:
            return SkillOutcome('FAILED', 'SHAPE_HAND', F.NOT_SUPPORTED,
                                'no verified named configuration for this embodiment')
        if abort_on_contact:
            return SkillOutcome('FAILED', 'SHAPE_HAND', F.SENSOR_UNAVAILABLE,
                                'mock cannot verify abort_on_contact')
        try:
            self.command_joint_targets(self.profile['postures'][semantic])
            self.step()
        except AdapterError as exc:
            return SkillOutcome('FAILED', 'SHAPE_HAND', exc.failure_class, str(exc))
        return SkillOutcome('SUCCESS', 'SHAPE_HAND',
            achieved_state={'semantic': semantic, 'joint_positions_rad': list(self._q)},
            residual_uncertainty=['object contact UNAVAILABLE', 'physical completion UNVERIFIED'],
            diagnostics={'backend': 'OFFLINE_JOINT_STATE_MOCK',
                         'completion': 'mock state transition only'})

    def dispatch_skill(self, name, *, goal=None, **kwargs):
        """Thin ISA gate. No task controller is hidden in this adapter."""
        if name == 'SHAPE_HAND':
            from dex_hand.skills.shape_posture import shape_hand
            return shape_hand(self, goal=goal, **kwargs)
        if name not in self.skill_status():
            return SkillOutcome('FAILED', name, F.NOT_SUPPORTED, 'unknown skill')
        return SkillOutcome('FAILED', name, F.NOT_SUPPORTED,
            'contact, load, object pose and safety evidence unavailable in this joint mock')
