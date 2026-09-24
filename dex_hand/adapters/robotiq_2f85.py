"""Robotiq 2F-85 offline adapter: one actuator, five source-defined mimics."""
import math

from dex_hand.core.observation import known, unknown
from dex_hand.core.outcome import AdapterError, FailureClass as F
from .offline_profile import OfflineProfileAdapter


class Robotiq2F85Adapter(OfflineProfileAdapter):
    profile_name = 'robotiq_2f85'

    def skill_status(self):
        return {
            'SHAPE_HAND': 'CONSTRAINED',
            'MAKE_CONTACT': 'UNVERIFIED',
            'ESTABLISH_GRASP': 'UNVERIFIED',
            'MAINTAIN_GRASP': 'UNVERIFIED',
            'BREAK_CONTACT': 'UNVERIFIED',
            'APPLY_WRENCH': 'UNVERIFIED',
            'MANIPULATE_IN_CONTACT': 'NOT_SUPPORTED',
            'CHANGE_CONTACTS': 'NOT_SUPPORTED',
            'FINGER_SPECIFIC_POSTURE': 'NOT_SUPPORTED',
        }

    def get_capabilities(self):
        result = super().get_capabilities()
        result['mimic_joints'] = self.profile['mimic_joints']
        result['direct_interface'] = ('get_state', 'set_gripper_target', 'stop')
        return result

    def set_gripper_target(self, position_rad):
        """ROS2 active knuckle command. There is no independent finger target."""
        return self.command_joint_targets([position_rad])

    def direct_set_joint_targets(self, targets):
        return self.command_joint_targets(targets)

    def get_gripper_state(self):
        t = float(self._tick)
        d = self._diagnostics
        # Exact opening requires standard fingers and parallel mode. A joint
        # angle alone is insufficient evidence of either condition.
        opening = (known(max(0.0, min(self.profile['max_opening_m'],
                    self.profile['max_opening_m'] *
                    (1-self._q[0]/self.profile['closed_position_rad']))), t,
                    'SDK_2F85_STANDARD_PARALLEL_PROFILE')
                   if d.get('parallel_mode_confirmed') is True and
                   d.get('standard_fingers_confirmed') is True else
                   unknown(t, 'FINGER_GEOMETRY_OR_PARALLEL_MODE_UNVERIFIED', unavailable=True))
        current = (known(d['motor_current_A'], t, 'ROBOTIQ_MOTOR_CURRENT_DIAGNOSTIC')
                   if d.get('motor_current_A') is not None else
                   unknown(t, 'MOTOR_CURRENT_NOT_IN_FAKE_STATE', unavailable=True))
        return {'active_joint': self.joints[0], 'position_rad': self._q[0],
                'velocity_rad_s': (known(self._velocity[0], t, self._velocity_provenance)
                    if self._velocity is not None else unknown(t, 'VELOCITY_NOT_MEASURED', unavailable=True)),
                'opening_m': opening, 'motor_current_A': current,
                'object_detection': d.get('object_detection', 'UNAVAILABLE'),
                'activation': d.get('activation', 'UNAVAILABLE'),
                'fault': self._fault, 'source': self._q_provenance}

    def get_hardware_health(self):
        result = super().get_hardware_health()
        result['activation'] = self._diagnostics.get('activation', 'UNAVAILABLE')
        result['object_detection'] = self._diagnostics.get('object_detection', 'UNAVAILABLE')
        return result

    def load_ros2_control_state(self, state):
        """Offline mapping of the official active-joint state interface.

        The real driver writes velocity=0 because gPO has no velocity field.
        That published zero must not become a valid measured velocity.
        """
        position = state.get('position_rad')
        try:
            position = float(position)
        except (TypeError, ValueError) as exc:
            raise AdapterError(F.PRECONDITION_FAILED, 'position_rad missing') from exc
        if not math.isfinite(position):
            raise AdapterError(F.PRECONDITION_FAILED, 'position_rad must be finite')
        current = state.get('motor_current_A')
        if current is not None:
            try:
                current = float(current)
            except (TypeError, ValueError) as exc:
                raise AdapterError(F.PRECONDITION_FAILED, 'motor_current_A invalid') from exc
            if not math.isfinite(current) or current < 0:
                raise AdapterError(F.PRECONDITION_FAILED, 'motor_current_A invalid')
        fault = state.get('gripper_fault')
        if fault in (None, 'UNAVAILABLE'):
            fault = None
        elif fault == 0:
            fault = None
        diagnostics = {key: state.get(key) for key in
            ('object_detection', 'activation', 'parallel_mode_confirmed',
             'standard_fingers_confirmed', 'gripper_fault_severity') if key in state}
        diagnostics['motor_current_A'] = current
        diagnostics['reported_velocity_rad_s'] = state.get('velocity_rad_s')
        diagnostics['velocity_note'] = 'official hardware interface exports synthetic zero'
        self.load_mock_feedback([position], velocity=None, diagnostics=diagnostics,
                                fault=fault,
                                fault_known='gripper_fault' in state and state['gripper_fault'] != 'UNAVAILABLE')
        self._q_provenance = 'ROBOTIQ_ROS2_CONTROL_STATE_OFFLINE_REPLAY'

    def load_status_registers(self, *, position, current, fault, object_detection,
                              activation='UNAVAILABLE'):
        """Offline decode of SDK gPO/gCU/gFLT fields; never opens Modbus."""
        for name, value in [('position',position),('current',current),('fault',fault)]:
            if not isinstance(value,int) or isinstance(value,bool) or not 0<=value<=255:
                raise AdapterError(F.PRECONDITION_FAILED, f'{name} must be byte')
        q = self.profile['closed_position_rad'] * (
            position-self.profile['register_open']) / (
            self.profile['register_closed']-self.profile['register_open'])
        self.load_ros2_control_state({'position_rad':q,
            'motor_current_A':current*self.profile['current_A_per_count'],
            'gripper_fault':fault or None, 'object_detection':object_detection,
            'activation':activation})
        self._q_provenance = 'ROBOTIQ_SDK_REGISTERS_OFFLINE_REPLAY'
