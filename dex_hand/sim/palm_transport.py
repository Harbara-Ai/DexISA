"""Generic arm/wrist motion, deliberately outside the hand Skill taxonomy."""
import math
import numpy as np


class PalmTransportController:
    position_tolerance=.001

    def __init__(self,adapter):
        self.a=adapter

    def move_linear(self,delta_xyz,speed=.02,accel_limit=.05,guard=None):
        delta=np.asarray(delta_xyz,float)
        distance=float(np.linalg.norm(delta))
        if speed<=0 or accel_limit<=0 or not np.isfinite(delta).all():raise ValueError('invalid motion profile')
        if distance==0:return 'REACHED'
        direction=delta/distance
        origin=self.a.wrist_target.copy()
        ramp=min(speed/accel_limit,math.sqrt(distance/accel_limit))
        peak=accel_limit*ramp
        cruise=max(0.,distance/peak-ramp)
        duration=2*ramp+cruise
        for i in range(1,math.ceil(duration/self.a.dt)+1):
            t=min(i*self.a.dt,duration)
            if t<ramp:s=.5*accel_limit*t*t;v=accel_limit*t
            elif t<ramp+cruise:s=.5*peak*ramp+peak*(t-ramp);v=peak
            else:
                left=duration-t;s=distance-.5*accel_limit*left*left;v=accel_limit*left
            self.a.wrist_target=origin+direction*s
            self.a.wrist_velocity=direction*v
            self.a.wrist_command={'kind':'move_linear','delta_xyz':delta.tolist(),'speed':speed,
                'accel_limit':accel_limit,'position':self.a.wrist_target.tolist(),'velocity':self.a.wrist_velocity.tolist()}
            self.a.step()
            event=guard() if guard else None
            if event:
                self.stop()
                return event
        self.a.wrist_velocity[:]=0
        return self.hold(.1,guard) or ('REACHED' if np.linalg.norm(
            self.a.data.qpos[self.a.transport_qids]-self.a.wrist_target)<=self.position_tolerance else 'PALM_TARGET_NOT_REACHED')

    def stop(self):
        # Position hold at the measured wrist location, never alter qpos.
        self.a.wrist_target=self.a.data.qpos[self.a.transport_qids].copy()
        self.a.wrist_velocity[:]=0
        self.a.wrist_command={'kind':'stop_hold','position':self.a.wrist_target.tolist(),'velocity':[0.,0.,0.]}

    def hold(self,duration,guard=None):
        self.a.wrist_velocity[:]=0
        self.a.wrist_command={'kind':'hold','duration':duration,'position':self.a.wrist_target.tolist(),'velocity':[0.,0.,0.]}
        for _ in range(math.ceil(duration/self.a.dt)):
            self.a.step()
            event=guard() if guard else None
            if event:self.stop();return event
        return None
