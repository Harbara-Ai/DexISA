"""One-shot, non-formal native Codex measurement; never enters benchmark tables."""
import sys, os, json, time, queue, threading, subprocess, shutil, hashlib
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / '.deps')]
OUT = ROOT / 'results_instrumentation_sanity'
PROMPT = ('Establish the requested contact safely using the available semantic robot tools.\n'
          'Use the minimum necessary tool calls.\n'
          'Stop once success or terminal failure is established.\n'
          'Do not explain; use tools directly.')
TOOLS = [dict(type='function', name=n, description=d,
              inputSchema={'type':'object','properties':{},'additionalProperties':False}) for n,d in [
    ('get_state','Read current canonical contact and safety state.'),
    ('describe_capabilities','Read supported contact capabilities and safety limits.'),
    ('MAKE_CONTACT','Establish primary-group contact with the supported nominal cylinder using the existing guarded approach and safety limits. The hand is already preshaped; stop on success or terminal failure.')]]
def save(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
def append(name, value):
    with (OUT/name).open('a', encoding='utf-8') as f: f.write(json.dumps(value, ensure_ascii=False)+'\n')
def stamp(): return {'unix_ns':time.time_ns(), 'monotonic_ns':time.perf_counter_ns()}
def shared():
    paths = list((ROOT/'dex_hand').rglob('*.py'))+[ROOT/'pilot/interfaces.py']+list((ROOT/'assets').rglob('*'))
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}

class Runtime:
    def __init__(self, prefix):
        self.prefix=prefix; self.q=queue.Queue(); self.seq=0
        class Receiver(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(handler):
                body=handler.rfile.read(int(handler.headers['Content-Length']))
                try: value=json.loads(body)
                except Exception: value={'decode_error':True,'bytes':len(body)}
                append(prefix+'_otel.jsonl', {'received':stamp(),'path':handler.path,'data':value})
                handler.send_response(200); handler.send_header('Content-Type','application/json'); handler.end_headers(); handler.wfile.write(b'{}')
        self.http=ThreadingHTTPServer(('127.0.0.1',0),Receiver)
        threading.Thread(target=self.http.serve_forever,daemon=True).start()
        endpoint=f'http://127.0.0.1:{self.http.server_port}'
        disabled=['shell_tool','view_image','sleep_tool','unified_exec','js_repl','code_mode','code_mode_only','multi_agent','multi_agent_v2','apps','plugins','browser_use','computer_use','image_generation','goals','token_budget','context_management','collaboration_modes','default_mode_request_user_input','send_async_message','send_message_to_user_async','skill_search','tool_search','apply_patch_freeform']
        self.config={**{'features.'+k:False for k in disabled},'web_search':'disabled','model_reasoning_effort':'low','project_doc_max_bytes':0,'mcp_servers':{},
            'otel.exporter':{'otlp-http':{'endpoint':endpoint+'/v1/logs','protocol':'json'}},
            'otel.trace_exporter':{'otlp-http':{'endpoint':endpoint+'/v1/traces','protocol':'json'}},'otel.log_user_prompt':False}
        args=[shutil.which('codex'),'app-server']
        # JSON objects are converted to TOML inline tables for command-line overrides.
        def toml(v):
            if isinstance(v,dict): return '{'+','.join(json.dumps(k)+'='+toml(x) for k,x in v.items())+'}'
            return json.dumps(v)
        for k,v in self.config.items(): args+=['-c',k+'='+toml(v)]
        self.err=(OUT/(prefix+'_runtime.stderr.log')).open('w',encoding='utf-8')
        self.p=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,encoding='utf-8',cwd=ROOT)
        def read():
            for line in self.p.stdout:
                try: msg=json.loads(line)
                except ValueError: continue
                record={'received':stamp(),'message':msg}; append(prefix+'_native_events.jsonl',record); self.q.put(record)
        threading.Thread(target=read,daemon=True).start()
        self.init=self.rpc('initialize',{'clientInfo':{'name':'instrumentation_sanity','version':'1.0'},'capabilities':{'experimentalApi':True}})
        self.send({'method':'initialized'})
    def send(self,msg):
        append(self.prefix+'_native_requests.jsonl',{'sent':stamp(),'message':msg})
        self.p.stdin.write(json.dumps(msg)+'\n');self.p.stdin.flush()
    def rpc(self,method,params):
        self.seq+=1; rid=self.seq;self.send({'id':rid,'method':method,'params':params})
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            r=self.q.get(timeout=max(.1,deadline-time.monotonic()));m=r['message']
            if m.get('id')==rid:
                if 'error' in m: raise RuntimeError(json.dumps(m['error']))
                return m['result']
        raise TimeoutError(method)
    def close(self):
        self.p.stdin.close()
        try:self.p.wait(timeout=12)
        except subprocess.TimeoutExpired:self.p.terminate();self.p.wait(timeout=5)
        self.http.shutdown();self.err.close()

def main():
    OUT.mkdir(exist_ok=True)
    preflight='--preflight' in sys.argv
    if not preflight:
        with (OUT/'episode_started.lock').open('x') as f:f.write(str(time.time_ns()))
    rt=Runtime('preflight' if preflight else 'episode')
    try:
        if preflight:
            models=rt.rpc('model/list',{'includeHidden':True})
            save('preflight.json',{'initialize':rt.init,'models':models})
            print(json.dumps({'initialize':rt.init,'luna':[m for m in models.get('data',[]) if 'luna' in str(m).lower()]}),flush=True)
            return
        run(rt)
    finally:rt.close()
    if not preflight:
        from summarize_instrumentation_sanity import main as summarize
        summarize()

def run(rt):
    from pilot.interfaces import PilotEpisode
    from dex_hand.skills.shape_hand import ShapeHand
    save('shared_before.json',shared());save('tool_schema.json',TOOLS)
    (OUT/'prompt.txt').write_text(PROMPT,encoding='utf-8')
    ep=PilotEpisode('B','wuji','SKILL_AGENT','nominal',OUT/'physical')
    setup=ShapeHand(ep.a).run('target',ep.groups,profile='PRESHAPE',aperture=.04)
    if not setup.success: raise RuntimeError('Existing preshape failed')
    initial={'qpos':ep.a.data.qpos.tolist(),'qvel':ep.a.data.qvel.tolist(),'ctrl':ep.a.data.ctrl.tolist(),
             'time':float(ep.a.data.time),'group_targets':{k:v.tolist() for k,v in ep.a.group_targets.items()},
             'xml_sha256':hashlib.sha256(ep.a.xml.encode()).hexdigest()}
    save('prepared_initial_state.json',initial)
    ep.trace.close();ep.trace=(OUT/'physical/episode_simulation.jsonl').open('w',encoding='utf-8')
    ep.sim_wall=ep.tool_wall=0.;ep.tool_trace=[];ep.calls=ep.queries=0
    ep.max_group_force=ep.max_drift=0.;ep.first_contact_time=None;ep.success=False
    prepared=stamp();sim_start=float(ep.a.data.time)
    save('episode_prepared.json',{'formal':False,'purpose':'instrumentation_sanity_check','timestamp':prepared,'sim_time_start':sim_start})
    thread=rt.rpc('thread/start',{'model':'gpt-5.6-luna','cwd':str(OUT),'approvalPolicy':'never','sandbox':'read-only',
        'baseInstructions':PROMPT,'developerInstructions':'','dynamicTools':TOOLS,'environments':[],
        'experimentalRawEvents':True,'allowProviderModelFallback':False})
    save('native_thread.json',thread)
    tid=thread['thread']['id']; first=stamp()
    rt.seq+=1;rt.send({'id':rt.seq,'method':'turn/start','params':{'threadId':tid,'model':'gpt-5.6-luna','effort':'low','input':[{'type':'text','text':PROMPT}]}})
    tools=[]; terminal=None; errors=[]; completed=False
    deadline=time.monotonic()+180
    try:
        while time.monotonic()<deadline:
            r=rt.q.get(timeout=max(.1,deadline-time.monotonic()));m=r['message'];method=m.get('method','');p=m.get('params',{})
            if 'error' in m: raise RuntimeError(str(m['error']))
            if method=='item/tool/call':
                name=p['tool'];args=p['arguments'];start=stamp();s0=float(ep.a.data.time)
                if terminal:raise RuntimeError('Tool requested after physical terminal outcome')
                if name not in {t['name'] for t in TOOLS}:raise RuntimeError('Unexpected tool '+name)
                if args:raise RuntimeError('Unexpected arguments')
                if name=='describe_capabilities':
                    result={'contact_group':'primary','object':'target','MAKE_CONTACT':'guarded inward approach from prepared no-contact state','max_group_load_N':4,'max_object_drift_m':.015,'local_feedback':True}
                else:result=ep.dispatch(name,{'fields':['contacts','object_relative_pose','status']} if name=='get_state' else {})
                end=stamp();rec={'turn_id':p['turnId'],'call_id':p['callId'],'tool':name,'arguments':args,'tool_start':start,'tool_end':end,'sim_time_start':s0,'sim_time_end':float(ep.a.data.time),'control_intervention':name=='MAKE_CONTACT','response':result}
                tools.append(rec);append('tool_trace.jsonl',rec)
                if ep.success or ep.shield_failure or result.get('status')=='FAILED' or result.get('failure'):terminal=end
                rt.send({'id':m['id'],'result':{'success':True,'contentItems':[{'type':'inputText','text':json.dumps(result)}]}})
            elif 'id' in m and 'method' in m:
                raise RuntimeError('Unexpected runtime request '+method)
            elif method=='turn/completed':
                completed=True
                if p['turn'].get('status')!='completed':errors.append(p['turn'])
                break
        if not completed:errors.append('Native turn did not complete')
    except Exception as e:errors.append(str(e))
    if terminal is None: terminal=stamp()
    physical=ep.finish('success' if ep.success else 'failure')
    save('execution.json',{'formal':False,'purpose':'instrumentation_sanity_check','thread_id':tid,'runtime_version':rt.init,'requested_model':'gpt-5.6-luna','reasoning_effort':'low',
        't_episode_prepared':prepared,'t_first_agent_request_dispatch':first,'t_terminal_outcome':terminal,'sim_time_start':sim_start,'sim_time_end':float(ep.a.data.time),'physical':physical,'errors':errors,'turn_completed':completed})
    save('shared_after.json',shared())
    print(json.dumps({'outcome':physical['outcome'],'tools':[t['tool'] for t in tools],'errors':errors}),flush=True)

if __name__=='__main__':main()
