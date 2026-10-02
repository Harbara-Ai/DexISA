"""Transport/profile WujiRealAdapter from the legacy real-hand backend.

Engineering dependencies are loaded when constructing this adapter:
``dex_hand.safety.real_hardware_safety`` and ``wuji_joint_map``. The optional
``execute_posture`` path also needs ``wuji_real_shape`` and its evaluator.
These engineering modules, profiles and SDK transports remain external to
this two-adapter source publication.

For the driver-injected V-sign pilot, use ``wuji2_real.WujiRealAdapter``.
That external driver owns the pilot's diagnostic-only receipt-age policy;
this legacy implementation preserves its separate historical guard policy.
Importing this module performs no hardware connection or motion.
"""
from dataclasses import asdict
import threading
import time
import sys
from dex_hand.core.observation import (CanonicalObservation, HandObservation,
    InteractionObservation, GraspObservation, Method, known, unknown)
from dex_hand.core.outcome import SkillOutcome, FailureClass as F
def _load_legacy_dependencies():
    """Resolve the original engineering dependencies before any device use."""
    global RealHardwareSafetyEnvelope, SafetyAbort, SafetyLimits, WujiRealJointMap
    try:
        from dex_hand.safety.real_hardware_safety import (
            RealHardwareSafetyEnvelope, SafetyAbort, SafetyLimits)
        from .wuji_joint_map import WujiRealJointMap
    except ModuleNotFoundError as exc:
        raise ImportError(
            'Legacy WujiRealAdapter requires the external real_hardware_safety '
            'and wuji_joint_map engineering modules. For the shared-driver '
            'pilot use dex_hand.adapters.wuji2_real.WujiRealAdapter.'
        ) from exc


class WujiRealAdapter:
    """Structural HandAdapter implementation; interaction primitives unsupported.

    read_raw_state/get_hardware_health are engineering-only diagnostics.
    CanonicalObservation preserves the existing top-level schema. Faults use
    the separate health interface because HandObservation has no fault slot.
    """
    def __init__(self, transport, profile, *, clock=time.monotonic, wall_clock=time.time,
                 sleep=time.sleep, trace=None):
        _load_legacy_dependencies()
        self.transport,self.profile = transport,profile
        self.clock,self.wall_clock,self.sleep = clock,wall_clock,sleep
        self.trace = trace or (lambda row: None)
        self.joint_map = WujiRealJointMap.from_profile(profile)
        self.safety = RealHardwareSafetyEnvelope(self.joint_map.bounds,SafetyLimits(**profile["safety_limits"]))
        self.dt = self.safety.limits.command_period_s
        self.active_modes,self.events,self.last_command = [],[],{}
        self.skill,self.phase = "IDLE","IDLE"
        self.grasp_verified,self.verified_groups,self.verified_reference = False,(),None
        self.callbacks = []
        self.armed = self.enable_attempted = False
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._watcher = None
        self.disable_confirmed = False
        self.monitor_error = None
        self.first_stop_reason = None
        self.stop_exception = None
        self.diagnostic_sink = None
        self.diagnostic_write_errors = []
        self.lifecycle = "DISARMED"
        self.last_raw_state = None

    def diagnostic(self,kind,**fields):
        row={"kind":kind,"timestamp":self.wall_clock(),"monotonic":self.clock(),
             "phase":self.phase,"lifecycle":self.lifecycle,"armed":self.armed,
             "stop_set":self._stop.is_set(),**fields}
        if self.diagnostic_sink:
            try:self.diagnostic_sink(row)
            except Exception as exc:
                self.diagnostic_write_errors.append(str(exc))
                print("DIAGNOSTIC PERSISTENCE FAILED: "+str(exc),file=sys.stderr,flush=True)
        return row

    def record_stop(self,exc,source):
        """Latch and synchronously persist the first cause before cleanup."""
        with self._lock:
            root=self.safety.latched or exc
            if self.first_stop_reason is None:
                self.stop_exception=root
                self.first_stop_reason={"code":getattr(root,"code","SDK_OR_CONTROLLER_ERROR"),
                    "detail":str(root),"source":source,"timestamp":self.wall_clock()}
                self.diagnostic("first_stop_reason",reason=self.first_stop_reason,
                    safety_events=list(self.safety.events),last_command=self.last_command,
                    last_raw_state=self.last_raw_state)
            else:
                self.diagnostic("secondary_error",source=source,detail=str(exc))
            return self.first_stop_reason

    def get_capabilities(self):
        return {"backend":"REAL_POSTURE_V1", "supported_skills":["SHAPE_HAND"],
            "supported_modes":[], "semantic_postures":[p for p,v in self.profile["postures"].items()
                if v["validation_status"] == "REAL_VALIDATED"],
            "engineering_candidates":[p for p,v in self.profile["postures"].items() if v["target_joint_configuration"] is not None],
            "contact_abort_available":False, "benchmark_ready":False}

    def get_observation_capabilities(self):
        return {"joint_position":{"source":"SDK_JOINT_POSITION","unit":"rad"},
            "joint_velocity":{"source":"SDK_JOINT_VELOCITY","unit":"rad/s"},
            "joint_effort":{"source":"MOTOR_CURRENT","unit":"A","method":"ESTIMATED","kind":"PROXY"},
            "hardware_fault":{"source":"SDK_ACTIVE_ERROR","interface":"get_fault_state"},
            "collision":"UNAVAILABLE","contact":"UNAVAILABLE","tactile":"UNAVAILABLE"}

    def read_raw_state(self):
        with self._lock:
            try:
                s = self.transport.read()
            except SafetyAbort:
                raise
            except Exception as exc:
                code = next((c for c in ("HARDWARE_FAULT","VELOCITY_LIMIT","EFFORT_OR_CURRENT_LIMIT","TARGET_OUT_OF_RANGE") if c in str(exc)),"COMMUNICATION_LOSS")
                self.safety.abort(code,str(exc))
            if s is None:
                raise SafetyAbort("COMMUNICATION_LOSS","State/diagnostics unavailable")
            s = dict(s)
            s["q"] = self.joint_map.from_sdk(s["q"])
            s["dq"] = self.joint_map.from_sdk(s["dq"],velocity=True)
            # Current is channel magnitude/sign from SDK, not a joint torque transform.
            s["current_a"] = [s["current_a"][e.index] for e in self.joint_map.entries]
            for key in ("temperature_c","voltage_v","fault_codes","enable_states"):
                s[key] = [s[key][e.index] for e in self.joint_map.entries]
            self.last_raw_state = s
            self.safety.check_state(s,self.clock(),self.wall_clock())
            return s

    def get_joint_positions(self): return self.read_raw_state()["q"]
    def get_joint_velocities(self): return self.read_raw_state()["dq"]
    def get_joint_efforts(self): return self.read_raw_state()["current_a"]

    def build_canonical_observation(self):
        s = self.read_raw_state()
        t = s["timestamp"]
        u = lambda: unknown(t,"REAL_SENSOR_UNAVAILABLE",unavailable=True)
        return CanonicalObservation(t,HandObservation(known(s["q"],t,"SDK_JOINT_POSITION"),
            known(s["dq"],t,"SDK_JOINT_VELOCITY"),
            known(s["current_a"],s["diag_timestamp"],"MOTOR_CURRENT_A_PROXY_NOT_TORQUE",Method.ESTIMATED),u(),u()),
            [],{},InteractionObservation(u(),u()),GraspObservation(u(),u()),list(self.active_modes))

    def get_fault_state(self):
        with self._lock:
            s = getattr(self.transport,"read_cleanup",self.transport.read)()
        if s is None:
            return {"available":False,"source":"SDK_ACTIVE_ERROR","active":None}
        fresh=(0<=self.clock()-s["diag_received_monotonic"]<=self.safety.limits.communication_timeout_s
               and abs(self.wall_clock()-s["diag_timestamp"])<=self.safety.limits.timestamp_age_s)
        return {"available":fresh,"source":"SDK_ACTIVE_ERROR","timestamp":s["diag_timestamp"],
                "active":any(s["fault_codes"]),"codes":s["fault_codes"]}

    def get_hardware_health(self):
        s = self.read_raw_state()
        return {"state":s,"metadata":self.transport.metadata,
                "safety_events":list(self.safety.events),"monitor_error":self.monitor_error}

    def precheck_motion(self, confirmation):
        required = ("workspace_clear","no_body_in_area","cables_clear","emergency_disable_available","hand_stable")
        if not confirmation or not all(confirmation.get(k) is True for k in required):
            raise SafetyAbort("PRECHECK_FAILED","Explicit current operator confirmation required")
        age = self.wall_clock()-confirmation.get("timestamp",0)
        if not 0 <= age <= 300 or confirmation.get("serial") != self.transport.metadata["serial"]:
            raise SafetyAbort("PRECHECK_FAILED","Confirmation expired or wrong device")
        if self.profile["motion_release_status"] != "ENGINEERING_APPROVED":
            raise SafetyAbort("PRECHECK_FAILED","Profile has unresolved engineering gates")
        if not self.transport.metadata.get("watchdog_verified",False):
            raise SafetyAbort("PRECHECK_FAILED","SAFETY_LIMIT_UNRESOLVED: device watchdog")
        if self.profile.get("joint_convention_validation") != "VERIFIED":
            raise SafetyAbort("PRECHECK_FAILED","Joint convention has not been validated")
        md = self.transport.metadata
        if md["serial"] != self.profile["serial"] or md["side"] != "right" or md["firmware_version"] != self.profile["firmware_version"]:
            raise SafetyAbort("PRECHECK_FAILED","Hardware profile identity/version mismatch")
        if md.get("joint_count") != 20 or len(md.get("soft_limits",[]))!=20:
            raise SafetyAbort("PRECHECK_FAILED","Incomplete joint metadata")
        limits = md["configured_current_limits_a"]
        if len(limits)!=20 or any(not 0 < x <= self.safety.limits.configured_current_max_a for x in limits):
            raise SafetyAbort("PRECHECK_FAILED","Current limits not conservatively configured")
        expected = self.profile["expected_mit_params"]
        if (len(md["mit_params"]) != 20 or len(expected) != 20 or
            any(len(a)!=2 or any(abs(x-y)>1e-6 for x,y in zip(a,b))
                for a,b in zip(md["mit_params"],expected))):
            raise SafetyAbort("PRECHECK_FAILED","Existing position-controller gains differ from approved profile")
        for e,soft in zip(sorted(self.joint_map.entries,key=lambda x:x.index),md["soft_limits"]):
            if not soft["enabled"]:
                raise SafetyAbort("PRECHECK_FAILED","Device soft limit disabled")
            sdk_ends = sorted(((e.safe_min-e.zero_offset)/e.sign,(e.safe_max-e.zero_offset)/e.sign))
            if sdk_ends[0] < soft["min"] or sdk_ends[1] > soft["max"]:
                raise SafetyAbort("PRECHECK_FAILED","Profile exceeds current device limits")
        s = self.read_raw_state()
        self.safety.check_state(s,self.clock(),self.wall_clock(),enabled=False)
        if max(abs(x) for x in s["dq"]) > self.safety.limits.initial_velocity_rad_s:
            raise SafetyAbort("PRECHECK_FAILED","Hand not stationary")
        return s

    def arm(self, confirmation):
        # A previous monitor must exit before a new arm clears the shared Event.
        if self._watcher and self._watcher is not threading.current_thread():
            self._stop.set()
            self._watcher.join()
        with self._lock:
            if self.stop_exception:raise self.stop_exception
            self.disable_confirmed=False
            self.lifecycle="ARMING"
            self.diagnostic("adapter_arm_requested")
            s = self.precheck_motion(confirmation)
            now = self.clock()
            q = self.safety.check_command(s["q"],s,now,self.wall_clock(),arming=True)
            self.transport.send(self.joint_map.to_sdk(q))
            self.safety.committed(q,now)
            self.enable_attempted = True
            try:
                self.diagnostic("hardware_enable_requested")
                self.transport.enable()
                deadline = self.clock()+1.0
                while self.clock()<deadline:
                    s = self.read_raw_state()
                    self.safety.watchdog(self.clock())
                    self.transport.send(self.joint_map.to_sdk(q))
                    self.safety.committed(q,self.clock())
                    if all(x==2 for x in s["enable_states"]):
                        self.armed = True
                        self.lifecycle="ARMED"
                        self.diagnostic("hardware_enable_confirmed",enable_states=s["enable_states"])
                        break
                    self.sleep(self.dt)
                if not self.armed:
                    raise SafetyAbort("HARDWARE_FAULT","Enable readback timeout")
            except BaseException as exc:
                self.record_stop(exc,"arm")
                try:self.disable()
                except BaseException as cleanup:self.record_stop(cleanup,"arm_cleanup")
                raise
        self._stop.clear()
        self._watcher = threading.Thread(target=self._monitor,daemon=True,name="real-hand-watchdog")
        self._watcher.start()

    def _monitor(self):
        while not self._stop.wait(self.dt):
            try:
                with self._lock:
                    self.safety.watchdog(self.clock())
                    self.read_raw_state()
            except Exception as exc:
                self.monitor_error = str(exc)
                self.record_stop(exc,"monitor")
                try:
                    self.disable()
                except Exception as stop_error:
                    self.monitor_error += "; disable: " + str(stop_error)
                    self.record_stop(stop_error,"monitor_cleanup")
                return

    def command_joint_targets(self, targets):
        with self._lock:
            if self.stop_exception:raise self.stop_exception
            if self.safety.latched:raise self.safety.latched
            if not self.armed or self._stop.is_set():
                raise SafetyAbort("PRECHECK_FAILED","Adapter not armed")
            s = self.read_raw_state()
            now = self.clock()
            q = self.safety.check_command(targets,s,now,self.wall_clock())
            try:
                self.transport.send(self.joint_map.to_sdk(q))
            except Exception as exc:
                self.safety.abort("COMMUNICATION_LOSS",str(exc))
            self.safety.committed(q,now)
            self.last_command = {"timestamp":self.wall_clock(),"target_q":list(q)}
            self.trace({"kind":"command",**self.last_command,"actual":s,"safety":"PASS"})
            return s

    command_joint_positions = command_joint_targets
    command_actuators = command_joint_targets

    def safe_hold(self):
        """One bounded hold attempt; disable if measurement needs an unsafe jump."""
        if not self.armed:
            return {"held":False,"reason":"not armed"}
        try:
            self.command_joint_targets(self.get_joint_positions())
            return {"held":True,"persistent":False}
        except Exception:
            self.disable()
            return {"held":False,"disabled":self.disable_confirmed}

    def disable(self):
        # Serialize cause persistence and transition with the command thread.
        with self._lock:
            if self.safety.latched and self.first_stop_reason is None:
                self.record_stop(self.safety.latched,"disable_entry")
            self.lifecycle="DISABLING"
            self.diagnostic("disable_requested",first_stop_reason=self.first_stop_reason)
            self._stop.set()
        if not self.enable_attempted:
            return False
        with self._lock:
            try:
                self.transport.disable()
            except Exception:
                self.transport.emergency_stop()
                raise
            self.armed = False
            deadline = self.clock()+1.0
            while self.clock()<deadline:
                # Cleanup read deliberately bypasses the latched motion guard.
                try:
                    s = getattr(self.transport,"read_cleanup",self.transport.read)()
                except Exception:
                    self.transport.emergency_stop()
                    raise
                if s and all(x==1 for x in s["enable_states"]):
                    if (self.clock()-s["diag_received_monotonic"] <= self.safety.limits.communication_timeout_s
                        and abs(self.wall_clock()-s["diag_timestamp"]) <= self.safety.limits.timestamp_age_s):
                        self.disable_confirmed = True
                        self.lifecycle="DISARMED"
                        self.diagnostic("disable_confirmed",enable_states=s["enable_states"])
                        self.trace({"kind":"disable","confirmed":True,"timestamp":self.wall_clock()})
                        return True
                self.sleep(self.dt)
            self.transport.emergency_stop()
            raise SafetyAbort("HARDWARE_FAULT","Disable not confirmed; emergency stop requested")

    def execute_posture(self, semantic, **kwargs):
        from .wuji_real_shape import WujiRealShapeController
        return WujiRealShapeController(self).run(semantic,**kwargs)

    def get_contact_groups(self): return ()
    def _unsupported(self,*args,**kwargs):
        from dex_hand.core.outcome import AdapterError
        raise AdapterError(F.NOT_SUPPORTED,"Real backend implements posture only")
    resolve_contact_group = get_contact_group_pose = prepare_configuration = advance_groups = _unsupported
    configuration_error = _unsupported
    def add_step_callback(self,callback): self.callbacks.append(callback)
    def remove_step_callback(self,callback): self.callbacks.remove(callback)
    def step(self,steps=1):
        for _ in range(steps):
            self.read_raw_state()
            for callback in tuple(self.callbacks): callback(self)
            self.sleep(self.dt)
