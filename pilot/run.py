"""Actual API-driven pilot. Refuses to substitute scripts or estimated usage."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.deps')]
import argparse,csv,hashlib,json,os,random,time,urllib.request
from pilot.interfaces import PilotEpisode,TASKS
from pilot.protocol import PROMPTS,TOOLS

OUT=ROOT/'results_pilot'
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def freeze_order():
    path=OUT/'pilot_run_order.json'
    if path.exists():return json.loads(path.read_text())
    rng=random.Random(24092026);pairs=[(t,h,'nominal') for t in 'ABCD' for h in ('wuji','sharpa')]
    pairs +=[(t,h,s) for t,s in [('B','recovery'),('C','safe_failure')] for h in ('wuji','sharpa')]
    rng.shuffle(pairs);episodes=[]
    for t,h,s in pairs:
        agents=['SKILL_AGENT','DIRECT_AGENT'];rng.shuffle(agents)
        for agent in agents:episodes.append({'episode_id':f'{t}_{h}_{s}_{agent}','task':t,'hand':h,'scenario':s,'agent':agent,'repeat':1})
    value={'seed':24092026,'episodes':episodes,'max_episodes':24,'status':'FROZEN_BEFORE_API_EXECUTION'}
    path.write_text(json.dumps(value,indent=2));return value

def parse_usage(response):
    u=response.get('usage')
    if not isinstance(u,dict) or any(not isinstance(u.get(k),int) for k in ('input_tokens','output_tokens','total_tokens')):
        raise ValueError('M3 unavailable: response did not contain authoritative API usage')
    return {'input_tokens':u['input_tokens'],'output_tokens':u['output_tokens'],'total_tokens':u['total_tokens'],
        'cached_input_tokens':u.get('input_tokens_details',{}).get('cached_tokens'),
        'reasoning_tokens':u.get('output_tokens_details',{}).get('reasoning_tokens')}

class ResponsesClient:
    def __init__(self):
        self.model=os.environ.get('PILOT_MODEL')
        self.reasoning=os.environ.get('PILOT_REASONING_EFFORT')
        self.key=os.environ.get('OPENAI_API_KEY')
        self.base=os.environ.get('OPENAI_BASE_URL','https://api.openai.com/v1').rstrip('/')
        if not all((self.model,self.reasoning,self.key)):raise RuntimeError('Configure PILOT_MODEL, PILOT_REASONING_EFFORT and OPENAI_API_KEY; no credentials are logged.')
    def response(self,payload):
        data={**payload,'model':self.model,'reasoning':{'effort':self.reasoning},'max_output_tokens':1200,
              'text':{'format':{'type':'json_object'}},'store':True}
        req=urllib.request.Request(self.base+'/responses',data=json.dumps(data).encode(),headers={
            'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=180) as r:return json.load(r)

def run_episode(spec,client):
    folder=OUT/'episodes'/spec['episode_id'];folder.mkdir(parents=True,exist_ok=True)
    if (folder/'result.json').exists():raise RuntimeError('Refusing to overwrite an executed episode')
    ep=PilotEpisode(spec['task'],spec['hand'],spec['agent'],spec['scenario'],folder)
    prompt=PROMPTS[spec['agent']];schemas=TOOLS[spec['agent']]
    # New API conversation for each episode. No cross-episode response IDs/history.
    payload={'input':[{'role':'system','content':prompt},{'role':'user','content':json.dumps({'tool_registry':schemas,**ep.static()})}]}
    total={'input_tokens':0,'output_tokens':0,'total_tokens':0,'cached_input_tokens':0,'reasoning_tokens':0}
    decisions=interventions=embodiment=usage_records=0;agent_time=0.;reported_model=None;claimed='failure';errors=[]
    started=time.perf_counter();conversation=(folder/'conversation.jsonl').open('w',encoding='utf-8')
    try:
        # Identical conservative stop budget for both agents; no scripted control.
        for _ in range(24):
            t=time.perf_counter();response=client.response(payload);elapsed=time.perf_counter()-t
            agent_time+=elapsed;decisions+=1
            conversation.write(json.dumps({'request':payload,'response':response,'agent_wall_s':elapsed})+'\n');conversation.flush()
            usage=parse_usage(response)
            usage_records+=1
            for k,v in usage.items():total[k]=None if v is None or total[k] is None else total[k]+v
            actual=response.get('model')
            if not actual:raise ValueError('Provider did not identify the model version')
            if reported_model is not None and actual!=reported_model:raise ValueError('Model changed during episode')
            reported_model=actual
            text=''.join(c.get('text','') for item in response.get('output',[]) if item.get('type')=='message' for c in item.get('content',[]) if c.get('type')=='output_text')
            action=json.loads(text)
            if not isinstance(action.get('embodiment_specific'),bool):raise ValueError('Missing decision classification boolean')
            embodiment+=int(action['embodiment_specific'])
            if 'result' in action:
                claimed=action['result'];break
            name=action['tool'];args=action.get('arguments',{})
            if name not in schemas:raise ValueError('Agent attempted a non-exposed tool')
            interventions+=1
            out=ep.dispatch(name,args)
            conversation.write(json.dumps({'action':action,'tool_output':out})+'\n')
            if ep.success:claimed='success';break
            # Carry server conversation ID. Static prompt/metadata/schema appear
            # only in the first message, but provider usage still counts context.
            payload={'previous_response_id':response['id'],'input':[{'role':'user','content':json.dumps({'tool_output':out})}]}
    except Exception as error:
        errors.append({'type':type(error).__name__,'detail':str(error)})
    finally:
        conversation.close();physical=ep.finish(claimed);elapsed=time.perf_counter()-started
    result={**spec,**physical,'prompt_hash':digest(prompt),'tool_schema_hash':digest(schemas),
        'requested_model':client.model,'reported_model':reported_model,'reasoning_effort':client.reasoning,
        'T_agent':agent_time,'T_end_to_end':elapsed,'tokens':total if decisions and usage_records==decisions else None,
        'N_agent_decisions':decisions,'N_agent_interventions':interventions,'N_tool_calls':ep.calls,'N_state_queries':ep.queries,
        'N_embodiment_specific_decisions':embodiment,'embodiment_specific_measure':'model boolean self-report; not observable hidden reasoning',
        'tool_schema_context_tokens':None,'tool_schema_context_tokens_reason':'No authoritative per-component token breakdown requested; never estimated',
        'errors':errors,'valid_for_comparison':not errors and reported_model is not None}
    (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');args=p.parse_args();order=freeze_order()
    for agent in PROMPTS:
        (OUT/(agent.lower()+'_prompt.txt')).write_text(PROMPTS[agent],encoding='utf-8')
        (OUT/(agent.lower()+'_tools.json')).write_text(json.dumps(TOOLS[agent],indent=2))
    if args.prepare:print('Frozen 24 paired episodes; no Agent calls executed.');return
    gates=json.loads((OUT/'preflight_gates.json').read_text())
    if not gates['formal_run_ready']:raise RuntimeError('Physical/interface preflight gates are not all satisfied; see preflight_gates.json')
    client=ResponsesClient();model=None
    for spec in order['episodes']:
        result=run_episode(spec,client)
        print(spec['episode_id'],result['outcome'],result['tokens'],flush=True)
        if not result['valid_for_comparison']:raise RuntimeError('Invalid usage/model/protocol: pilot stopped, raw trace preserved')
        if model is None:model=result['reported_model']
        elif model!=result['reported_model']:raise RuntimeError('Cross-episode model mismatch: stop rather than compare different versions')
        if spec['task']=='A' and spec['agent']=='DIRECT_AGENT' and not result['physical_success']:
            raise RuntimeError('Check A failed: Direct SHAPE did not work; stop and review baseline fairness')

if __name__=='__main__':main()
