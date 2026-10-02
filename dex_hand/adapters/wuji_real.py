"""Driver-injected WujiRealAdapter for the Wuji2 real-hand pilot.

The shared driver script, SDK and engineering profile are external dependencies
supplied by the caller. Importing this module does not connect to hardware.

The external, shared driver owns device lifecycle and all retained protections.
Generic finger shaping generates targets here, never in evaluation.
"""
import json
import math
import subprocess
from pathlib import Path

from dex_hand.core.observation import (CanonicalObservation, HandObservation,
    InteractionObservation, GraspObservation, Method, known, unknown)
from dex_hand.core.outcome import AdapterError, FailureClass, SkillOutcome

FINGERS = ('thumb', 'index', 'middle', 'ring', 'pinky')


class DriverError(RuntimeError):
    def __init__(self, error):
        super().__init__(error['detail'])
        self.code = error['code']


class Wuji2DriverClient:
    def __init__(self, *, python, legacy_root, directory, fake=False):
        self.seq = 0
        self.closed = False
        self.failed = False
        command = [str(python), '-u', str(Path(legacy_root) / 'scripts/wuji2_pilot_driver.py'),
                   '--directory', str(directory)]
        if fake:
            command.append('--fake')
        self.stderr = Path(str(directory) + '_worker_stderr.log').open('x', encoding='utf-8')
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.stderr, text=True, encoding='utf-8', bufsize=1)

    def rpc(self, op, **args):
        if self.failed or self.closed:
            raise RuntimeError('Driver unavailable after terminal fault/close')
        self.seq += 1
        self.process.stdin.write(json.dumps({'id': self.seq, 'op': op, 'args': args}, allow_nan=False) + '\n')
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            self.failed = True
            raise RuntimeError('Driver EOF; inspect raw worker and bridge logs')
        reply = json.loads(line)
        if reply['id'] != self.seq:
            self.failed = True
            self.process.stdin.close()
            raise RuntimeError('Driver response pairing failed')
        if not reply['ok']:
            self.failed = True
            raise DriverError(reply['error'])
        return reply['data']

    def close(self):
        if self.closed:
            return
        try:
            if not self.failed and self.process.poll() is None:
                self.rpc('close')
        finally:
            self.closed = True
            if not self.process.stdin.closed:
                self.process.stdin.close()
            self.process.wait()  # Device cleanup must complete, never kill its owner silently.
            self.process.stdout.close()
            self.stderr.close()


class WujiRealAdapter:
    time_domain = 'wall'
    dt = .01  # Existing command_period_s, not a new timing limit.

    def __init__(self, driver):
        self.driver = driver
        self.active_modes, self.events, self.last_command = [], [], {}
        self.skill = self.phase = 'IDLE'
        self.grasp_verified = False
        self.verified_groups = ()
        self.verified_reference = None
        self.metadata = driver.rpc('describe_hand')

    def get_capabilities(self):
        return {
            'backend': 'WUJI2_SDK_REAL', 'supported_skills': ['SHAPE_HAND'],
            'supported_modes': [], 'named_gesture_presets': [],
            'SHAPE_HAND': {'hand_shape': {
                'curl': 'Optional finger-name -> fraction in [0,1]. Zero is model-native zero flexion; one is existing flexion upper bound minus existing margin.',
                'abduction_rad': 'Optional finger-name -> native abduction radians. Unspecified channels retain their current command.',
            }, 'duration_s': 'Agent-selected bounded position-command interval; no gesture evaluator or success-based stopping.'},
            'mapping_validation': self.metadata['anatomical_mapping_validation'],
            'residual_uncertainty': 'Anatomical SDK zero/sign mapping and collision safety are unverified; there is no camera/contact feedback.',
            'gesture_judgement': 'PENDING_HUMAN',
            'target_slew_rad_s': self.metadata['target_slew_rad_s'],
        }

    def get_observation_capabilities(self):
        from dataclasses import dataclass
        @dataclass
        class Capability:
            source: str
            unit: str
        return {'joint_position': Capability('SDK_JOINT_POSITION', 'rad'),
                'joint_velocity': Capability('SDK_JOINT_VELOCITY', 'rad/s'),
                'joint_effort': Capability('MOTOR_CURRENT_PROXY', 'A')}

    def read_raw_state(self):
        return self.driver.rpc('state')

    def build_canonical_observation(self):
        s = self.read_raw_state()
        t = s['timestamp']
        missing = lambda: unknown(t, 'REAL_SENSOR_UNAVAILABLE', unavailable=True)
        return CanonicalObservation(t, HandObservation(
            known(s['q'], t, 'SDK_JOINT_POSITION'), known(s['dq'], t, 'SDK_JOINT_VELOCITY'),
            known(s['current_a'], s['diag_timestamp'], 'MOTOR_CURRENT_PROXY_A', Method.ESTIMATED),
            missing(), missing()), [], {}, InteractionObservation(missing(), missing()),
            GraspObservation(missing(), missing()), [])

    def get_joint_positions(self):
        return self.read_raw_state()['q']

    def get_joint_velocities(self):
        return self.read_raw_state()['dq']

    def get_joint_efforts(self):
        return self.read_raw_state()['current_a']

    def shape_free_space(self, hand_shape, duration_s):
        if not isinstance(hand_shape, dict) or not hand_shape or set(hand_shape) - {'curl', 'abduction_rad'}:
            raise ValueError('hand_shape requires curl and/or abduction_rad')
        targets = {}
        margin = self.metadata['host_boundary_margin_rad']
        bounds = self.metadata['joint_bounds_rad']
        for operand, values in hand_shape.items():
            if not isinstance(values, dict) or not values:
                raise ValueError('Finger operands must be nonempty mappings')
            for finger, value in values.items():
                if finger not in FINGERS or isinstance(value, bool) or not math.isfinite(float(value)):
                    raise ValueError('Invalid finger/value')
                offset = 4 * FINGERS.index(finger)
                if operand == 'curl':
                    if not 0 <= value <= 1:
                        raise ValueError('curl is a normalized fraction')
                    # Generic model-native flexion coordinate map from the existing profile.
                    # These are command-generation operands, not safety gates or a gesture recipe.
                    for local in (0, 2, 3):
                        lo, hi = bounds[offset + local]
                        if not lo + margin <= 0 <= hi - margin:
                            raise AdapterError(FailureClass.NOT_SUPPORTED, 'Zero flexion outside existing profile')
                        targets[str(offset + local)] = float(value) * (hi - margin)
                else:
                    targets[str(offset + 1)] = float(value)
        result = self.driver.rpc('move', targets=targets, duration_s=duration_s)
        return SkillOutcome('SUCCESS', 'SHAPE_HAND',
            achieved_state={'command_interval_completed': True},
            residual_uncertainty=['gesture quality is pending human judgement',
                                  'anatomical SDK mapping unverified', 'collision/contact sensing unavailable'],
            diagnostics={'execution': result, 'generated_targets': targets,
                         'target_generation_source': 'existing profile flexion upper bounds and 0.02 rad boundary margin',
                         'success_semantics': 'command interval completed; not a gesture score'})

    def safe_hold(self):
        return self.driver.rpc('stop')

    def step(self, steps=1):
        raise AdapterError(FailureClass.NOT_SUPPORTED, 'No simulation stepping on this real adapter')
