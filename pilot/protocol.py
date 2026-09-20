"""Short prompts; JSON action protocol keeps static schemas in initial context only."""
COMMON='''Use minimal decisions. Output only one JSON action or final result, no explanation.
Choose from the provided tool registry; no code execution, outside tools or hidden helpers.
Respect joint and force limits. Static metadata is supplied once; do not request it again.
Read compact canonical state only when useful. Use meaningful action durations, not tiny-step polling.
After a structured action failure attempt at most one reasonable recovery; do not increase force after a safety stop.
Stop when the task succeeds or safe impossibility is established. A common evaluator checks success at action boundaries;
it does not stop your motion on contact. A common safety shield may interrupt unsafe actions. Unknown values are not zero.
get_state.wait_s advances simulation while any local mode continues. Simulation pauses during model inference.
Joint servo dynamics and effort caps are identical in both conditions. Physical simulation seconds are not wall-clock seconds.
For grasp certification the benchmark applies the same small perturbation when stability is detected; this is not an agent controller.
Return {"tool":"name","arguments":{...},"embodiment_specific":false} or
{"result":"success|safe_failure|failure","embodiment_specific":false}.
Set embodiment_specific=true only when this decision explicitly depends on the supplied hand-specific joint layout
or kinematics. This boolean is a self-report, not a request to reveal reasoning.
'''
PROMPTS={
 'SKILL_AGENT':'You control a dexterous hand through semantic skills and a local feedback mode.\n'+COMMON+
    'Skill actions use the task object and contact groups supplied in metadata. SHAPE_HAND selects POINT or PRESHAPE. Mode enter starts local regulation; query reads it; exit stops it. Other Skills cannot run while the mode is active, except controlled release. Tool names state their physical purpose; they do not certify arbitrary task feasibility.',
 'DIRECT_AGENT':'You control a dexterous hand through joint targets and canonical observations.\n'+COMMON+
    'set_joint_targets accepts any number of indexed joint targets together. Unspecified joints retain their last targets. It runs only the existing finite-effort position servos for duration seconds; it has no IK, approach controller, contact regulation or grasp state machine. Use joint definitions and kinematic transforms supplied once. stop holds measured posture. You may hold an unchanged target by issuing it with a longer duration.'}

SHARED={'get_state':{'fields':'optional subset of contacts, object_relative_pose, joint_state, status','wait_s':'optional 0..1 simulation seconds, default 0'}}
TOOLS={
 'SKILL_AGENT':{**SHARED,'describe_capabilities':{},'SHAPE_HAND':{'profile':'POINT or PRESHAPE'},'MAKE_CONTACT':{},'ESTABLISH_GRASP':{},
    'MAINTAIN_GRASP_enter':{},'MAINTAIN_GRASP_query':{},'MAINTAIN_GRASP_exit':{},'APPLY_WRENCH':{},'BREAK_CONTACT':{}},
 'DIRECT_AGENT':{**SHARED,'describe_hand':{},'set_joint_targets':{'targets':'object mapping joint indices to target radians; multiple joints allowed','duration':'.02..2 simulation seconds'},'stop':{}}}
