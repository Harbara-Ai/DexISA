import csv
import json
import numpy as np
from pathlib import Path
from dataclasses import asdict


class ExperimentLog:
    """50 Hz CSV snapshots plus per-step maxima and unsampled outcome/events."""
    def __init__(self, adapter, path, stride=10):
        self.a=adapter
        path=Path(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        self.file=path.open("w",newline="",encoding="utf-8")
        self.writer=csv.DictWriter(self.file,fieldnames=["timestamp","skill","phase","q","dq","effort","contacts","normal_loads",
            "object_world_pose","object_relative_pose","grasp_state","active_modes","command","failure_events","canonical_observation"])
        self.writer.writeheader()
        self.stride=stride
        self.steps=0
        self.max_load=0.
        self.max_group_load=0.
        self.max_drift=0.
        self.transitions=[]
        self.last_groups=set()
        self.reference=None
        adapter.add_step_callback(self.tick)
        self.tick(adapter.build_canonical_observation(),force=True)

    def tick(self,o,force=False):
        self.steps+=1
        groups={c.contact_group_id for c in o.contacts}
        if groups!=self.last_groups:
            self.transitions.append({"timestamp":o.timestamp,"from":sorted(self.last_groups),"to":sorted(groups)})
            self.last_groups=groups
            force=True
        self.max_load=max(self.max_load,max((c.normal_load.value for c in o.contacts if c.normal_load.valid),default=0.))
        self.max_group_load=max(self.max_group_load,max((sum(c.normal_load.value for c in o.contacts if c.contact_group_id==g and c.normal_load.valid) for g in groups),default=0.))
        obj=o.objects.get("target")
        if obj and obj.relative_pose.valid:
            p=np.array(obj.relative_pose.value.position)
            if self.reference is None:self.reference=p
            self.max_drift=max(self.max_drift,float(np.linalg.norm(p-self.reference)))
        if not force and self.steps%self.stride:return
        j=lambda x:json.dumps(x,ensure_ascii=False,separators=(",",":"))
        self.writer.writerow({"timestamp":o.timestamp,"skill":self.a.skill,"phase":self.a.phase,
            "q":j(o.hand.joint_position.value),"dq":j(o.hand.joint_velocity.value),"effort":j(o.hand.joint_effort.value),
            "contacts":j([asdict(c) for c in o.contacts]),"normal_loads":j([c.normal_load.value for c in o.contacts]),
            "object_world_pose":j(asdict(obj.pose)) if obj else "null","object_relative_pose":j(asdict(obj.relative_pose)) if obj else "null",
            "grasp_state":j(asdict(o.grasp.state)),"active_modes":j(o.active_modes),"command":j(self.a.last_command),
            "failure_events":j(self.a.events),"canonical_observation":j(o.to_dict())})

    def summary(self):
        return {"max_contact_load_n":self.max_load,"max_group_normal_load_n":self.max_group_load,"max_object_drift_m":self.max_drift,"contact_transitions":self.transitions,
                "metric_rate_hz":1/self.a.dt,"csv_rate_hz":1/(self.a.dt*self.stride)}

    def close(self):
        self.tick(self.a.build_canonical_observation(),force=True)
        self.a.remove_step_callback(self.tick)
        self.file.close()
