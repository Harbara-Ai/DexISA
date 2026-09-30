"""One Direct episode paired with the immutable Skill instrumentation baseline."""
import sys, json, time, hashlib, queue
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT),str(ROOT/'.deps')]
import instrumentation_sanity as native
OUT=ROOT/'results_wuji_contact_direct_single'
BASE=ROOT/'results_instrumentation_sanity'
PROMPT='''You control a dexterous hand using low-level joint targets and canonical observations.
Establish the requested contact safely.
Use feedback to decide when to continue or stop.
You may command multiple joints at once.
Use the minimum necessary observations and actions.
Stop once success or terminal failure is established.
Do not explain; use tools directly.'''
TASK=('Establish contact between the primary contact group and the side of the supported cylinder. '
      'Stop after the first legal contact. Keep object drift within 0.015 m, group load below 4 N, '
      'and avoid unrelated collisions. The palm is fixed and the initial preshape is already prepared.')
EMPTY={'type':'object','properties':{},'additionalProperties':False}
def tool(n,d,s=EMPTY):
    return {'type':'function','name':n,'description':d+' Returns structured JSON; display the entire returned value with text(result) in the native code transport.', 'inputSchema':s}
TOOLS=[
    tool('describe_hand','Read joint names, limits, axes and basic kinematics once; subsequent calls do not repeat metadata.'),
    tool('get_state','Read compact canonical joint positions, contact/load, object drift and collision/safety state. Does not advance simulation.'),
    tool('set_joint_targets','Set any number of indexed joint targets in radians together and run the existing finite-effort position servos for duration seconds. Unspecified joints retain prior targets. No IK, contact advance or contact-triggered stopping. Returns current compact state at the action boundary.',
         {'type':'object','properties':{'targets':{'type':'object','additionalProperties':{'type':'number'}},'duration':{'type':'number','minimum':.02,'maximum':2}},'required':['targets','duration'],'additionalProperties':False}),
    tool('stop','Hold the measured posture using the existing low-level API; return current compact state.')]
def save(n,v):native.save(n,v)
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def file_hashes(folder):return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}

def observation(ep,relevant):
    import numpy as np
    o=ep.a.build_canonical_observation()
    value=ep.compact(['contacts','object_relative_pose','status'])
    # Preserve the same compact contact/object fields as Skill, add Direct-required data.
    value.update(joint_positions={str(i):round(float(o.hand.joint_position.value[i]),6) for i in relevant},
        joint_velocities={str(i):round(float(o.hand.joint_velocity.value[i]),6) for i in relevant},
        primary_normal_load_N=sum(c.normal_load.value for c in o.contacts if c.contact_group_id=='primary'),
        object_drift_m=float(np.linalg.norm(ep.a.data.xpos[ep.a.object_id]-ep.initial_object)),
        max_object_drift_m=ep.max_drift,collision=o.hand.collision.value,shield_failure=ep.shield_failure,
        required_contact_established=ep.success and not bool(ep.shield_failure))
    return value

def run():
    from pilot.interfaces import PilotEpisode
    from dex_hand.skills.shape_hand import ShapeHand
    OUT.mkdir(exist_ok=True);native.OUT=OUT
    with (OUT/'episode_started.lock').open('x') as f:f.write(str(time.time_ns()))
    baseline=load(BASE/'instrumentation_sanity_result.json')
    if baseline['instrumentation_gate']!='PASS':raise RuntimeError('Skill instrumentation baseline gate is not PASS')
    baseline_hashes=file_hashes(BASE);save('baseline_files_before.json',baseline_hashes)
    implementation=native.shared();save('shared_before.json',implementation)
    if implementation!=load(BASE/'shared_after.json'):raise RuntimeError('Shared implementation changed; no inference or Direct action allowed')
    save('run_config.json',{'formal':False,'purpose':'single_pair_comparison','requested_model':'gpt-5.6-luna','reasoning_effort':'low',
        'episodes':1,'baseline_reused':str(BASE/'instrumentation_sanity_result.json'),
        'benchmark_terminal_timeout_s':180,'timeout_origin':'first native turn/start dispatch, as in Skill runner',
        'direct_physical_timeout_s':None,'common_joint_velocity_threshold':None,'contact_triggered_direct_stop':False,
        'prompt_sha256':digest(PROMPT),'tool_schema_sha256':digest(TOOLS)})
    save('tool_schema.json',TOOLS);(OUT/'prompt.txt').write_text(PROMPT,encoding='utf-8')
    ep=PilotEpisode('B','wuji','DIRECT_AGENT','nominal',OUT/'physical')
    setup=ShapeHand(ep.a).run('target',ep.groups,profile='PRESHAPE',aperture=.04)
    if not setup.success:raise RuntimeError('Existing setup failed; no inference or Direct action allowed')
    initial={'qpos':ep.a.data.qpos.tolist(),'qvel':ep.a.data.qvel.tolist(),'ctrl':ep.a.data.ctrl.tolist(),
        'time':float(ep.a.data.time),'group_targets':{k:v.tolist() for k,v in ep.a.group_targets.items()},
        'xml_sha256':hashlib.sha256(ep.a.xml.encode()).hexdigest()}
    save('prepared_initial_state.json',initial)
    reference=load(BASE/'prepared_initial_state.json')
    equivalent=initial==reference
    save('initial_equivalence.json',{'initial_state_equivalent':equivalent,'direct_initial_state_sha256':digest(initial),
        'skill_initial_state_sha256':digest(reference),'scene_xml_sha256':initial['xml_sha256'],
        'skill_scene_xml_sha256':reference['xml_sha256'],'shared_sources_match':True})
    if not equivalent:raise RuntimeError('Initial state mismatch; no inference or Direct action allowed')
    ep.trace.close();ep.trace=(OUT/'physical/episode_simulation.jsonl').open('w',encoding='utf-8')
    ep.sim_wall=ep.tool_wall=0.;ep.tool_trace=[];ep.calls=ep.queries=0
    ep.max_group_force=ep.max_drift=0.;ep.first_contact_time=None;ep.success=False
    relevant=[i for i,j in enumerate(ep.a.joints) if ep.a.model.body(ep.a.model.jnt_bodyid[j]).name.startswith(ep.a.group_map['primary'])]
    initial_obs=observation(ep,relevant);save('initial_observation.json',initial_obs)
    prepared=native.stamp();sim_start=float(ep.a.data.time)
    save('episode_prepared.json',{'timestamp':prepared,'sim_time_start':sim_start})
    rt=None;thread=None;first=None;terminal=None;errors=[];completed=False;timed_out=False;events=[];described=False
    try:
        rt=native.Runtime('episode')
        thread=rt.rpc('thread/start',{'model':'gpt-5.6-luna','cwd':str(OUT),'approvalPolicy':'never','sandbox':'read-only',
            'baseInstructions':PROMPT,'developerInstructions':'','dynamicTools':TOOLS,'environments':[],
            'config':{'features.skip_host_skill_discovery':True},'experimentalRawEvents':True,'allowProviderModelFallback':False})
        save('native_thread.json',thread)
        if thread['model']!='gpt-5.6-luna' or thread.get('reasoningEffort')!='low':raise RuntimeError('Resolved model/effort mismatch; stopped before inference')
        inp={'task':TASK,'initial_observation':initial_obs,'benchmark_terminal_timeout_s':180}
        save('task_input.json',inp)
        first=native.stamp();deadline=time.monotonic()+180
        rt.seq+=1;rt.send({'id':rt.seq,'method':'turn/start','params':{'threadId':thread['thread']['id'],'model':'gpt-5.6-luna','effort':'low','input':[{'type':'text','text':json.dumps(inp)}]}})
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0:timed_out=True;break
            try:r=rt.q.get(timeout=remaining)
            except queue.Empty:timed_out=True;break
            m=r['message'];method=m.get('method','');p=m.get('params',{})
            if 'error' in m:raise RuntimeError(str(m['error']))
            if 'rerouted' in method.lower():raise RuntimeError('Native model rerouted; stopped')
            if method=='item/tool/call':
                name=p['tool'];args=p['arguments']
                if name not in {t['name'] for t in TOOLS}:raise RuntimeError('Non-exposed tool '+name)
                start=native.stamp();s0=float(ep.a.data.time)
                if name=='describe_hand':
                    if described:result={'metadata_already_provided':True}
                    else:
                        static=ep.static()
                        result={k:static[k] for k in ['joint_definitions','kinematic_chain','sites','palm_native_world_pose','object']}
                        result['primary_joint_indices']=relevant
                        result['safety']={'max_group_load_N':4,'max_object_drift_m':.015,'joint_effort_limits':'see joint_definitions','independent_joint_velocity_threshold':None}
                        described=True
                else:
                    result=ep.dispatch(name,{'fields':['contacts','object_relative_pose','status']} if name=='get_state' else args)
                    if name=='get_state':result=observation(ep,relevant)
                    elif 'state' in result:result['state']=observation(ep,relevant)
                end=native.stamp()
                rec={'index':len(events)+1,'turn_id':p['turnId'],'call_id':p['callId'],'tool':name,'arguments':args,
                     'tool_start':start,'tool_end':end,'sim_time_start':s0,'sim_time_end':float(ep.a.data.time),
                     'control_intervention':name in ['set_joint_targets','stop'],'response':result}
                events.append(rec);native.append('tool_trace.jsonl',rec)
                # No early stop on contact: the complete requested command has already executed.
                rt.send({'id':m['id'],'result':{'success':True,'contentItems':[{'type':'inputText','text':json.dumps(result)}]}})
                print(json.dumps({'tool':name,'sim_s':float(ep.a.data.time)-sim_start,'contact':ep.success,'shield':ep.shield_failure}),flush=True)
            elif 'method' in m and 'id' in m:raise RuntimeError('Unexpected runtime request '+method)
            elif method=='turn/completed':
                terminal=r['received'];completed=True
                if p['turn']['status']!='completed':errors.append(p['turn'])
                break
        if timed_out:
            terminal=native.stamp();ep.a.safe_hold()
            rt.seq+=1;rt.send({'id':rt.seq,'method':'turn/interrupt','params':{'threadId':thread['thread']['id'],'turnId':events[-1]['turn_id'] if events else ''}})
    except Exception as e:errors.append({'type':type(e).__name__,'detail':str(e)})
    finally:
        if terminal is None:terminal=native.stamp()
        final_observation=observation(ep,relevant)
        physical=ep.finish('success' if ep.success and not ep.shield_failure else 'failure')
        save('execution.json',{'formal':False,'purpose':'single_pair_comparison','requested_model':'gpt-5.6-luna',
            'thread_id':thread['thread']['id'] if thread else None,'reasoning_effort':'low',
            'runtime':rt.init if rt else None,'t_episode_prepared':prepared,'t_first_agent_request_dispatch':first,'t_terminal_outcome':terminal,
            'sim_time_start':sim_start,'sim_time_end':float(ep.a.data.time),'physical':physical,'terminal_observation':final_observation,
            'errors':errors,'turn_completed':completed,'benchmark_timeout_triggered':timed_out,
            'explicit_agent_stop':any(e['tool']=='stop' for e in events)})
        if rt:rt.close()
        save('shared_after.json',native.shared());save('baseline_files_after.json',file_hashes(BASE))
    from summarize_wuji_contact_direct_single import main as summarize
    summarize()

if __name__=='__main__':run()
