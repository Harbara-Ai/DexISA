"""Allegro Hand V5 4F right-B offline adapter, with official 16-joint map."""
from dex_hand.core.outcome import AdapterError, FailureClass as F
from .offline_profile import OfflineProfileAdapter, _vector


class AllegroV5Adapter(OfflineProfileAdapter):
    profile_name = 'allegro_v5'

    def skill_status(self):
        return {
            'SHAPE_HAND': 'CONSTRAINED',
            'MAKE_CONTACT': 'UNVERIFIED',
            'ESTABLISH_GRASP': 'UNVERIFIED',
            'MAINTAIN_GRASP': 'UNVERIFIED',
            'BREAK_CONTACT': 'UNVERIFIED',
            'APPLY_WRENCH': 'UNVERIFIED',
            'MANIPULATE_IN_CONTACT': 'UNVERIFIED',
            'CHANGE_CONTACTS': 'UNVERIFIED',
        }

    def load_joint_state(self, message):
        """Offline conversion of a ROS JointState-shaped mapping, no ROS import."""
        names = message.get('name')
        if not isinstance(names, (list, tuple)) or len(names) != len(set(names)):
            raise AdapterError(F.PRECONDITION_FAILED, 'joint names missing or duplicated')
        if set(names) != set(self.joints):
            raise AdapterError(F.PRECONDITION_FAILED, 'expected exact official 16-joint set')
        positions = _vector(message.get('position'), len(names), label='joint position')
        index = {name: i for i, name in enumerate(names)}
        positions = [positions[index[name]] for name in self.joints]
        velocity = message.get('velocity')
        if velocity is not None and len(velocity) > 0:
            velocity = _vector(velocity, len(names), label='joint velocity')
            velocity = [velocity[index[name]] for name in self.joints]
        else:
            velocity = None
        effort = message.get('effort')
        # Official node publishes desired_torque as JointState.effort; it is
        # command diagnostic, not measured load/torque.
        desired = _vector(effort, len(names), label='desired torque') if effort is not None and len(effort) else None
        desired = None if desired is None else [desired[index[name]] for name in self.joints]
        self.load_mock_feedback(positions, velocity=velocity,
            diagnostics={'desired_torque_Nm': desired,
                         'desired_torque_provenance': 'ROS_JOINT_STATE_EFFORT_IS_DESIRED_TORQUE'},
            fault=None)
        self._q_provenance = 'ALLEGRO_ROS_JOINT_STATE_OFFLINE_REPLAY'
        if velocity is not None:
            self._velocity_provenance = 'ALLEGRO_ROS_JOINT_STATE_OFFLINE_REPLAY'
