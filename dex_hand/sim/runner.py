from dataclasses import asdict
from pathlib import Path
import json
import time
from dex_hand.adapters import create_adapter
from dex_hand.core.types import PINCH_GROUPS, PRESS_GROUPS
from dex_hand.core.outcome import AdapterError, SkillOutcome, FailureClass
from dex_hand.core.schema import validate_outcome
from dex_hand.skills.shape_hand import ShapeHand
from dex_hand.skills.make_contact import MakeContact
from dex_hand.skills.establish_grasp import EstablishGrasp
from dex_hand.skills.apply_wrench import ApplyWrench
from dex_hand.skills.break_contact import BreakContact
from dex_hand.modes.maintain_grasp import MaintainGrasp
from .worlds import WorldConfig
from .perturbation import MujocoPerturbation
from .logging import ExperimentLog


def run_experiment(hand="wuji", test="grasp", config=None, output="results", gui=False, label=None):
    config=config or (WorldConfig(kind="button",center=(.025,.065,.24)) if test=="button" else WorldConfig())
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    label=label or f"{hand}_{test}"
    start=time.perf_counter()
    try:
        a=create_adapter(hand,config=config)
    except AdapterError as error:
        out=SkillOutcome("FAILED","BACKEND_INITIALIZATION",error.failure_class,str(error))
        validate_outcome(out)
        result={"hand":hand,"test":test,"status":"NOT_SUPPORTED","failure_class":"NOT_SUPPORTED","outcomes":[out.to_dict()],"schema_valid":True,
                "cross_embodiment_executed":False}
        (output/f"{label}.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        return result
    viewer=None
    if gui:
        import mujoco.viewer
        viewer=mujoco.viewer.launch_passive(a.model,a.data)
        viewer.cam.lookat[:]=(.02,.05,.25)
        viewer.cam.distance=.45
        viewer.cam.azimuth=135
        viewer.cam.elevation=-20
        def sync(o):
            if viewer.is_running():viewer.sync()
            time.sleep(a.dt)
        a.add_step_callback(sync)
    log=ExperimentLog(a,output/f"{label}.csv")
    (output/f"{label}.world.xml").write_text(a.xml,encoding="utf-8")
    probe=MujocoPerturbation(a)
    mode=MaintainGrasp(a)
    outcomes=[]
    disturbance=[]
    g=PRESS_GROUPS if test=="button" else PINCH_GROUPS
    def record(out):
        validate_outcome(out)
        outcomes.append(out)
        log.tick(a.build_canonical_observation(),force=True)
        return out.success
    try:
        stages=[lambda:ShapeHand(a).run("target",g,profile="POINT" if test=="button" else "PRESHAPE",aperture=2*config.radius),
                lambda:MakeContact(a).run("target",g),
                lambda:ApplyWrench(a).run("target",g) if test=="button" else EstablishGrasp(a,probe).run("target",g)]
        completed=True
        for stage in stages:
            if not record(stage()):
                completed=False
                break
        if completed and test!="button":
            completed=record(mode.enter("target",g))
            if completed:
                a.skill="MAINTAIN_GRASP"
                a.phase="HOLD"
                for _ in range(int(.75/a.dt)):
                    a.step()
                    if not mode.active:break
                if not mode.active:
                    record(SkillOutcome("FAILED","MAINTAIN_GRASP",mode.event["failure_class"],mode.event["failure_detail"]))
                    completed=False
            if completed and test=="disturbance":
                for force in (0.,.5,1.,2.,4.):
                    a.phase=f"DISTURBANCE_{force}N"
                    probe.set_wrench(force=(force,0,0))
                    for _ in range(int(.5/a.dt)):
                        a.step()
                        if not mode.active:break
                    probe.clear()
                    disturbance.append({"force_x_n":force,"health":mode.query(),"observation":a.build_canonical_observation().to_dict()})
                    if not mode.active:
                        record(SkillOutcome("FAILED","MAINTAIN_GRASP",mode.event["failure_class"],mode.event["failure_detail"]))
                        completed=False
                        break
                    # Observe autonomous recovery between independent force levels.
                    for _ in range(int(.3/a.dt)):
                        a.step()
                        if not mode.active:break
                    if not mode.active:
                        record(SkillOutcome("FAILED","MAINTAIN_GRASP",mode.event["failure_class"],mode.event["failure_detail"]))
                        completed=False
                        break
        if completed:
            completed=record(BreakContact(a).run("target",g,support_state="FIXTURE" if test=="button" else "SURFACE",retreat=.02 if test=="button" else .012))
        result={"hand":hand,"test":test,"config":asdict(config),"status":"SUCCESS" if completed else "FAILED",
                "failure_class":next((o.failure_class for o in outcomes if not o.success),None),
                "outcomes":[o.to_dict() for o in outcomes],"v02_outcomes":[o.to_v02() for o in outcomes],
                "schema_valid":True,"capabilities":a.get_capabilities(),"observation_capabilities":{k:asdict(v) for k,v in a.get_observation_capabilities().items()},
                "mode_health":mode.query(),"disturbance_levels":disturbance,"failure_events":a.events,
                "simulation_time_s":float(a.data.time),"wall_time_s":time.perf_counter()-start,
                "mujoco_warning_count":sum(w.number for w in a.data.warning),**log.summary()}
    finally:
        probe.clear()
        mode.exit()
        log.close()
        if viewer:viewer.close()
    (output/f"{label}.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    return result
