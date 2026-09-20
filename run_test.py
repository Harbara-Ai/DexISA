"""Same experiment graph for every adapter; only registry selects embodiment."""
import argparse
import json
import sys
from pathlib import Path

# Optional local dependency installation; normal pip install -e . also works.
local_deps=Path(__file__).parent/".deps"
if local_deps.is_dir():sys.path.insert(0,str(local_deps))
from dex_hand.sim.runner import run_experiment
from dex_hand.sim.worlds import WorldConfig


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--hand",choices=["wuji","sharpa"],default="wuji")
    parser.add_argument("--test",choices=["grasp","disturbance","button","matrix","all"],default="all")
    parser.add_argument("--output",default="results")
    parser.add_argument("--gui",action="store_true")
    parser.add_argument("--radius",type=float,default=.02)
    parser.add_argument("--height",type=float,default=.025)
    parser.add_argument("--mass",type=float,default=.06)
    parser.add_argument("--friction",type=float,default=.7)
    args=parser.parse_args()
    jobs=[]
    if args.test in ("all","matrix"):
        for size,radius in (("small",.015),("medium",.02),("large",.025)):
            for friction,mu in (("low",.2),("medium",.7),("high",1.2)):
                jobs.append(("grasp",WorldConfig(radius=radius,height=args.height,mass=args.mass,friction=mu),f"{args.hand}_{size}_{friction}"))
    if args.test=="all":jobs.extend([(t,None,None) for t in ("disturbance","button")])
    elif args.test!="matrix":
        config=None if args.test=="button" else WorldConfig(radius=args.radius,height=args.height,mass=args.mass,friction=args.friction)
        jobs.append((args.test,config,None))
    summaries=[]
    for test,config,label in jobs:
        r=run_experiment(args.hand,test,config,args.output,args.gui,label)
        summary={k:r.get(k) for k in ("hand","test","status","failure_class","simulation_time_s","max_contact_load_n","max_object_drift_m")}
        summary["label"]=label or f"{args.hand}_{test}"
        summaries.append(summary)
        print(json.dumps(summary),flush=True)
        if r["status"]=="NOT_SUPPORTED":break
    Path(args.output,f"{args.hand}_{args.test}_summary.json").write_text(json.dumps(summaries,indent=2),encoding="utf-8")
    return 2 if any(r["status"]=="NOT_SUPPORTED" for r in summaries) else 1 if any(r["status"]!="SUCCESS" for r in summaries) else 0


if __name__=="__main__":raise SystemExit(main())
