"""Local transport for four native Codex CONTACT contexts; no external model API."""
import sys,json,time,hashlib,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'.deps')]
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.request import Request,urlopen

OUT=ROOT/'results_contact_native'
PORT=18764
EPISODES={}

def sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def serve():
    from pilot.interfaces import PilotEpisode
    from dex_hand.skills.shape_hand import ShapeHand
    OUT.mkdir(exist_ok=True)
    original=json.loads((ROOT/'results_pilot/pilot_run_order.json').read_text())
    order=[x for x in original['episodes'] if x['task']=='B' and x['scenario']=='nominal']
    (OUT/'run_order.json').write_text(json.dumps(order,indent=2))
    shared={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'dex_hand').rglob('*.py')}
    (OUT/'shared_before.json').write_text(json.dumps(shared,indent=2))
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            try:
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                key=data['episode'];op=data['operation']
                if op=='begin':
                    if key in EPISODES:raise ValueError('Episode already exists; no reruns')
                    spec=next(x for x in order if x['episode_id']==key)
                    folder=OUT/key
                    if (folder/'result.json').exists():raise ValueError('Refusing to overwrite a completed episode')
                    ep=PilotEpisode('B',spec['hand'],spec['agent'],'nominal',folder)
                    out=ShapeHand(ep.a).run('target',ep.groups,profile='PRESHAPE',aperture=.04)
                    if not out.success:raise RuntimeError('Preshape setup failed: '+str(out.to_dict()))
                    initial={'qpos':ep.a.data.qpos.tolist(),'qvel':ep.a.data.qvel.tolist(),'ctrl':ep.a.data.ctrl.tolist(),
                        'time':float(ep.a.data.time),'group_targets':{k:v.tolist() for k,v in ep.a.group_targets.items()},
                        'xml_sha256':hashlib.sha256(ep.a.xml.encode()).hexdigest()}
                    (folder/'prepared_initial_state.json').write_text(json.dumps(initial,indent=2))
                    ep.trace.close();ep.trace=(folder/'episode_simulation.jsonl').open('w',encoding='utf-8')
                    ep.sim_wall=ep.tool_wall=0.;ep.tool_trace=[];ep.calls=ep.queries=0
                    ep.max_group_force=ep.max_drift=0.;ep.first_contact_time=None;ep.success=False
                    relevant=[i for i,j in enumerate(ep.a.joints) if ep.a.model.body(ep.a.model.jnt_bodyid[j]).name.startswith(ep.a.group_map['primary'])]
                    EPISODES[key]={'ep':ep,'spec':spec,'start':time.perf_counter(),'start_sim':float(ep.a.data.time),
                        'events':[],'described':False,'relevant':relevant,'initial_hash':sha(initial),'finished':False}
                    result={'ready':True,'prepared_initial_hash':sha(initial),'allowed_tools':(['get_state','describe_capabilities','MAKE_CONTACT'] if spec['agent']=='SKILL_AGENT' else ['describe_hand','get_state','set_joint_targets','stop'])}
                elif op=='tool':
                    state=EPISODES[key];ep=state['ep'];name=data['tool'];args=data.get('arguments',{})
                    allowed=['get_state','describe_capabilities','MAKE_CONTACT'] if ep.condition=='SKILL_AGENT' else ['describe_hand','get_state','set_joint_targets','stop']
                    if state['finished']:raise ValueError('Episode finished')
                    if name not in allowed:raise ValueError('Tool not exposed in this condition')
                    if len(state['events'])>=32:raise ValueError('Common 32-action episode budget exhausted; submit failure')
                    t=time.perf_counter()
                    if name=='describe_hand':
                        if state['described']:result={'static_metadata':'Already provided once; consult prior response.'}
                        else:
                            metadata=ep.static()
                            result={k:metadata[k] for k in ('joint_definitions','kinematic_chain','sites','palm_native_world_pose')}
                            result['primary_joint_indices']=state['relevant']
                            result['object']={'shape':'cylinder','radius':.020,'height':.025,'mass':.060,
                                'world_position':ep.nominal_center.tolist(),'friction':1.2}
                            result['initial_joint_positions']={str(i):float(q) for i,q in enumerate(ep.a.get_joint_positions())}
                            result['safety']={'max_group_load_N':4,'max_object_drift_m':.015,'effort_caps':'original; per-joint definitions above'}
                            state['described']=True
                    elif name=='describe_capabilities':
                        result={'contact_group':'primary','object':'target','MAKE_CONTACT':'guarded inward approach from prepared no-contact state',
                            'max_group_load_N':4,'max_object_drift_m':.015,'local_feedback':True}
                    elif name=='get_state':
                        ep.dispatch(name,{'fields':['contacts','object_relative_pose','status']})
                        o=ep.a.build_canonical_observation()
                        result={'time_since_start_s':round(float(ep.a.data.time)-state['start_sim'],6),
                            'joint_positions':{str(i):round(float(o.hand.joint_position.value[i]),6) for i in state['relevant']},
                            'joint_velocities':{str(i):round(float(o.hand.joint_velocity.value[i]),6) for i in state['relevant']},
                            'primary_normal_load_N':sum(c.normal_load.value for c in o.contacts if c.contact_group_id=='primary'),
                            'contacts':[{'group':c.contact_group_id,'normal_load_N':round(c.normal_load.value,6),'position_world':c.position.value['xyz']} for c in o.contacts],
                            'object_relative_pose':{'position':o.objects['target'].relative_pose.value.position,'quaternion':o.objects['target'].relative_pose.value.quaternion_wxyz},
                            'object_drift_m':ep.max_drift,'collision':o.hand.collision.value,'safety_event':ep.shield_failure,
                            'required_contact_established':any(c.contact_group_id=='primary' for c in o.contacts)}
                    else:
                        answer=ep.dispatch(name,args)
                        if name=='MAKE_CONTACT':result=answer
                        else:
                            # No new observation until Direct explicitly queries.
                            result={'accepted':not bool(answer.get('failure')),'executed_duration_s':args.get('duration',0)}
                            if answer.get('failure'):result.update(failure=answer['failure'],detail=answer.get('detail'))
                    elapsed=time.perf_counter()-t
                    event={'index':len(state['events'])+1,'tool':name,'arguments':args,'response':result,
                        'tool_wall_s':elapsed,'elapsed_wall_s':time.perf_counter()-state['start'],
                        'sim_time':float(ep.a.data.time),'embodiment_specific_visible_action':name=='set_joint_targets'}
                    state['events'].append(event)
                    with (ep.folder/'visible_tool_trace.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(event)+'\n')
                elif op=='finish':
                    state=EPISODES[key];ep=state['ep']
                    if state['finished']:raise ValueError('Already finished')
                    end=time.perf_counter();physical=ep.finish(data.get('claim','failure'))
                    events=state['events'];tool=sum(x['tool_wall_s'] for x in events)
                    result={**state['spec'],**physical,'model':'gpt-5.6-luna','reasoning_effort':'low',
                        'prepared_initial_hash':state['initial_hash'],'T_end_to_end':end-state['start'],
                        'T_tool':tool,'T_agent':end-state['start']-tool,
                        'T_agent_definition':'Residual: native model inference + native transport/orchestration overhead; not pure inference latency',
                        'T_physical_sim':float(ep.a.data.time)-state['start_sim'],
                        'tokens':{'input_tokens':'UNAVAILABLE','output_tokens':'UNAVAILABLE','total_tokens':'UNAVAILABLE',
                            'cached_tokens':'UNAVAILABLE','reasoning_tokens':'UNAVAILABLE'},
                        'N_agent_decisions':len(events)+1,'N_agent_interventions':len(events),
                        'N_tool_calls':len(events),'N_state_queries':sum(x['tool']=='get_state' for x in events),
                        'N_joint_command_calls':sum(x['tool']=='set_joint_targets' for x in events),
                        'embodiment_specific_agent_decisions':sum(x['embodiment_specific_visible_action'] for x in events),
                        'decision_count_basis':'One sequential robot-tool request per decision plus terminal result submission; final administrative acknowledgement excluded',
                        'visible_final_claim':data.get('claim'),'visible_trace':[x['tool'] for x in events]}
                    (ep.folder/'result.json').write_text(json.dumps(result,indent=2))
                    state['finished']=True
                    result={'recorded':True,'outcome':result['outcome'],'failure':ep.shield_failure,'robot_tool_calls':len(events)}
                else:raise ValueError('Unknown transport operation')
                body=json.dumps(result).encode();self.send_response(200)
            except Exception as e:
                body=json.dumps({'transport_error':type(e).__name__,'detail':str(e)}).encode();self.send_response(400)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    print('Local CONTACT bridge ready',flush=True)
    HTTPServer(('127.0.0.1',PORT),Handler).serve_forever()

def client():
    # One request per CLI invocation; stdin JSON, no command sequencing.
    operation=sys.argv[1];key=sys.argv[2]
    payload={'operation':operation,'episode':key}
    if operation=='tool':payload.update(json.loads(sys.stdin.read()))
    if operation=='finish':payload['claim']=sys.argv[3]
    req=Request(f'http://127.0.0.1:{PORT}',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    try:
        with urlopen(req,timeout=120) as r:print(r.read().decode())
    except Exception as e:
        if hasattr(e,'read'):print(e.read().decode())
        else:raise

if __name__=='__main__':
    if sys.argv[1]=='serve':serve()
    else:client()
