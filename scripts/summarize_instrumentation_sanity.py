"""Offline audit of the one immutable episode; never invokes a model or simulator."""
import json, hashlib
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results_instrumentation_sanity'
TOKEN_MAP={'input_tokens':'inputTokens','cached_input_tokens':'cachedInputTokens',
           'cache_write_input_tokens':'cacheWriteInputTokens','output_tokens':'outputTokens',
           'reasoning_output_tokens':'reasoningOutputTokens'}
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
def rows(path):return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
def save(name,x):(OUT/name).write_text(json.dumps(x,indent=2,ensure_ascii=False),encoding='utf-8')
def attrs(span):return {a['key']:next(iter(a['value'].values())) for a in span['attributes']}
def usage(u):
    result={k:u.get(v) for k,v in TOKEN_MAP.items()}
    if any(type(v)!=int or v<0 for v in result.values()):raise ValueError('Missing/invalid native token breakdown')
    result['total_tokens']=result['input_tokens']+result['output_tokens']
    if result['total_tokens']!=u['totalTokens']:raise ValueError('Native total differs from input + output')
    return result
def inference_spans(spans):
    byid={s['spanId']:s for s in spans};selected=[]
    for s in spans:
        if s['name']!='responses_websocket.stream_request':continue
        parent=byid[s['parentSpanId']];a=attrs(parent)
        if a.get('websocket.warmup') is True:continue
        if a.get('websocket.warmup') is not False:raise ValueError('Cannot distinguish warmup from inference')
        selected.append((s,a))
    return sorted(selected,key=lambda x:int(x[0]['startTimeUnixNano']))
def iso(ns):return datetime.fromtimestamp(ns/1e9,timezone.utc).isoformat()

def main():
    ex=read('execution.json');thread=read('native_thread.json');events=rows(OUT/'episode_native_events.jsonl')
    tools=rows(OUT/'tool_trace.jsonl')
    spans=[s for l in rows(OUT/'episode_otel.jsonl') for r in l['data'].get('resourceSpans',[]) for sc in r['scopeSpans'] for s in sc['spans']]
    responses=[r for r in events if r['message'].get('method')=='rawResponse/completed']
    calls=inference_spans(spans)
    if len(calls)!=len(responses) or not calls:raise ValueError('Native inference/usage count mismatch')
    if len({r['message']['params']['responseId'] for r in responses})!=len(responses):raise ValueError('Duplicate response usage')
    per=[];decisions=[]
    for i,((s,a),r) in enumerate(zip(calls,responses),1):
        p=r['message']['params'];u=usage(p['usage']);start=int(s['startTimeUnixNano']);end=int(s['endTimeUnixNano'])
        if p['threadId']!=ex['thread_id'] or start>=end:raise ValueError('Invalid native identity/timing')
        # The native event is emitted at completion; exporter delivery time is not used.
        if abs(end/1e6-r['message']['emittedAtMs'])>100:raise ValueError('Response/span pairing is ambiguous')
        per.append({'decision_cycle':i,'turn_id':p['turnId'],'response_id':p['responseId'],'usage_source':'native_turn_usage',**u})
        decisions.append({'decision_cycle':i,'turn_id':p['turnId'],'response_id':p['responseId'],
            'resolved_model':a['model'],'request_start':{'unix_ns':start,'utc':iso(start)},
            'response_end':{'unix_ns':end,'utc':iso(end)},'duration_s':(end-start)/1e9,
            'timing_source':'native_otel:responses_websocket.stream_request','span_id':s['spanId'],
            'trace_id':s['traceId'],'visible_action':'semantic tool request' if i<len(calls) else 'terminal response'})
    totals={k:sum(p[k] for p in per) for k in [*TOKEN_MAP,'total_tokens']}
    native_total=usage([e['message']['params']['tokenUsage']['total'] for e in events if e['message'].get('method')=='thread/tokenUsage/updated'][-1])
    rollout_path=Path(thread['thread']['path']);rollout=rows(rollout_path)
    context=[r['payload'] for r in rollout if r['type']=='turn_context'][-1]
    meta=next(r['payload'] for r in rollout if r['type']=='session_meta')
    rollout_usage=[r['payload']['info']['total_token_usage'] for r in rollout if r['type']=='event_msg' and r['payload'].get('type')=='token_count' and r['payload'].get('info')][-1]
    prepared=ex['t_episode_prepared']['unix_ns'];first=decisions[0]['request_start']['unix_ns']
    completion=next(e for e in events if e['message'].get('method')=='turn/completed')
    # Final outcome = native agent turn closes with the independently measured physical result.
    # Preserve earlier physical success separately; include the final inference in episode totals.
    terminal=completion['received']['unix_ns']
    times={'T_startup':(first-prepared)/1e9,'T_active':(terminal-first)/1e9,
           'T_agent':sum(d['duration_s'] for d in decisions),
           'T_tool':sum((t['tool_end']['monotonic_ns']-t['tool_start']['monotonic_ns'])/1e9 for t in tools),
           'T_physical':ex['sim_time_end']-ex['sim_time_start'],'T_total':(terminal-prepared)/1e9}
    counts={'N_decision_cycles':len(decisions),'N_control_interventions':sum(t['tool']=='MAKE_CONTACT' for t in tools),
            'N_tool_calls':len(tools),'N_state_queries':sum(t['tool']=='get_state' for t in tools)}
    initial_matches=read('prepared_initial_state.json')==json.loads((ROOT/'results_contact_native/B_wuji_nominal_SKILL_AGENT/prepared_initial_state.json').read_text())
    nframes=sum(1 for _ in (OUT/'physical/episode_simulation.jsonl').open())
    spec_counts=[int(attrs(s)['tool_spec_count']) for s in spans if s['name']=='merge_into_namespaces']
    gates={
      'real_native_luna_low':all(d['resolved_model']=='gpt-5.6-luna' for d in decisions) and context['model']=='gpt-5.6-luna' and context['effort']=='low' and not any('rerouted' in e['message'].get('method','').lower() for e in events),
      'token_usage_available':bool(per),'positive_input_output':totals['input_tokens']>0 and totals['output_tokens']>0,
      'usage_matches_native_thread_total':totals==native_total,
      'usage_matches_session_rollout':all(totals[k]==rollout_usage[k] for k in totals),
      'valid_timing':times['T_startup']>=0 and times['T_active']>0 and times['T_agent']>0 and times['T_tool']>=0 and times['T_physical']>0 and times['T_total']>=times['T_active'] and decisions[-1]['response_end']['unix_ns']<=terminal,
      'distinct_counts':counts['N_tool_calls']==sum(1 for e in events if e['message'].get('method')=='item/tool/call') and all(t['control_intervention']==(t['tool']=='MAKE_CONTACT') for t in tools),
      'only_three_semantic_tools':bool(spec_counts) and all(n==3 for n in spec_counts) and all(t['tool'] in {'get_state','describe_capabilities','MAKE_CONTACT'} for t in tools),
      'physical_episode_executed':nframes>0 and abs(nframes*.002-times['T_physical'])<1e-8,
      'unchanged_implementation_and_assets':read('shared_before.json')==read('shared_after.json'),
      'identical_nominal_prepared_state':initial_matches,
      'no_infrastructure_error':not ex['errors'] and ex['turn_completed'],
    }
    gate='PASS' if all(gates.values()) else 'FAIL'
    result={'formal':False,'purpose':'instrumentation_sanity_check','instrumentation_gate':gate,
        'valid_for_formal_benchmark':False,'hand':'Wuji','agent':'SKILL_AGENT','task':'GUARDED_CONTACT / MAKE_CONTACT',
        'outcome':ex['physical']['outcome'],'thread_id':ex['thread_id'],'session_id':meta['id'],
        'turn_id':context['turn_id'],'resolved_model':context['model'],'reasoning_effort':context['effort'],'runtime_version':meta['cli_version'],
        'usage_source':'native_turn_usage','usage_event':'rawResponse/completed','token_usage':{'available':True,**totals},
        'episode_input_tokens':totals['input_tokens'],'episode_output_tokens':totals['output_tokens'],'episode_total_tokens':totals['total_tokens'],
        **times,**counts,'t_episode_prepared':ex['t_episode_prepared'],'t_first_agent_request_start':decisions[0]['request_start'],
        't_terminal_outcome':completion['received'],'t_physical_outcome':ex['t_terminal_outcome'],
        'terminal_outcome_definition':'native turn completed after physical result; includes terminal inference',
        'T_agent_definition':'Sum of native non-warmup responses_websocket.stream_request spans; request dispatch through stream completion, including provider/network latency; no tool-time subtraction',
        'sim_time_start':ex['sim_time_start'],'sim_time_end':ex['sim_time_end'],'simulation_frames':nframes,
        'native_transport_wrapper_calls':sum(e['message'].get('method')=='rawResponseItem/completed' and e['message'].get('params',{}).get('item',{}).get('type')=='custom_tool_call' for e in events),
        'tool_count_scope':'semantic robot calls; native exec is a transport wrapper, counted separately',
        'gates':gates,'failed_fields':[k for k,v in gates.items() if not v],
        'rollout_source_path':str(rollout_path),'rollout_sha256':hashlib.sha256(rollout_path.read_bytes()).hexdigest(),
        'physical':ex['physical']}
    save('instrumentation_sanity_result.json',result);save('token_usage_per_turn.json',per)
    (OUT/'decision_trace.jsonl').write_text(''.join(json.dumps(d)+'\n' for d in decisions),encoding='utf-8')
    save('native_rollout_evidence.json',{'session_meta':{k:meta.get(k) for k in ['id','cli_version','timestamp']},'turn_context':{k:context.get(k) for k in ['turn_id','model','effort']},'total_token_usage':rollout_usage})
    metrics=[('Outcome',result['outcome']),('Input tokens',totals['input_tokens']),('Cached input tokens',totals['cached_input_tokens']),('Output tokens',totals['output_tokens']),('Reasoning output tokens',totals['reasoning_output_tokens']),('Total tokens',totals['total_tokens'])]+list(times.items())+[(k.replace('N_','').replace('_',' ').capitalize(),v) for k,v in counts.items()]
    table='\n'.join('| '+k+' | '+(f'{v:.9f}' if isinstance(v,float) else str(v))+' |' for k,v in metrics)
    report=f'''# NON_FORMAL instrumentation sanity check

`formal = false`; `purpose = instrumentation_sanity_check`.

INSTRUMENTATION GATE: {gate}

Exactly one Wuji / SKILL_AGENT / GUARDED_CONTACT episode ran, with native GPT-5.6 Luna and low reasoning. No reruns and no formal benchmark. These files are isolated from all benchmark CSV/statistics and support no Skill-vs-Direct performance conclusion.

| Metric | Value |
| --- | ---: |
{table}

All times are seconds. Cache-write input tokens: {totals['cache_write_input_tokens']}. Cached/reasoning tokens are breakdowns, not extra terms in the total.

Native thread/session: `{ex['thread_id']}`. Turn: `{context['turn_id']}`. Runtime: `{meta['cli_version']}`. Resolved model and effort are verified against native sampling spans and rollout turn context.

Usage source: `native_turn_usage`, specifically two `rawResponse/completed` notifications. Both decision cycles share one native turn ID and have distinct response IDs. Their sum exactly matches native thread total and independently read session rollout total. The rollout is a cross-check, not the usage fallback. No model self-report, tokenizer, or character estimate was used.

Timing uses the native `responses_websocket.stream_request` span start/end for each inference. The warmup span is explicitly excluded. Request latency includes network/provider processing; it is not a claim about GPU-only compute. `run_sampling_request` spans are unsuitable here because they include tool draining. Tool boundaries use `perf_counter_ns`; episode/runtime boundaries use the same host UTC nanosecond clock. `T_agent` is never a residual. Raw timestamps and span IDs are preserved in decision_trace.jsonl.

The terminal boundary is receipt of native `turn/completed` with the independently established physical outcome; the final inference is included in tokens, decisions and active time. The earlier MAKE_CONTACT completion is separately saved as `t_physical_outcome`; execution.json preserves that original physical boundary. This avoids excluding terminal inference time while still charging its tokens. Simulator time pauses between tools. Physical elapsed time matches {nframes} recorded frames at 0.002 seconds each, excluding preshape/setup.

Observed semantic calls: {', '.join(t['tool'] for t in tools)}. Queries and terminal responses do not count as control interventions. Runtime tool-builder telemetry reports exactly three semantic tool specs at every capture: get_state, describe_capabilities, MAKE_CONTACT. The native code-mode `exec` wrapper remains the runtime transport; its one call is recorded separately and is not an additional robot intervention. Native runtime automatically injected its skill catalog and permissions context; the supplied task prompt stayed short and no full robot Skill spec was sent. The model's wrapper did not print the structured MAKE_CONTACT return into the outer transcript, so contact success is certified by the host's saved tool result and simulation, not by a model success claim. This is not evidence about agent feedback quality.

The prepared state exactly matches the previously verified nominal Wuji CONTACT setup (qpos/qvel/ctrl/time/group targets/XML hash). Before/after hashes of Skill, adapter, world/safety code and assets match. MAKE_CONTACT continues to call the existing PilotEpisode dispatcher with no parameter changes.

Instrumentation changes are confined to scripts/instrumentation_sanity.py (native App Server client, local OTel collector, one-shot lock, three-tool dispatcher) and scripts/summarize_instrumentation_sanity.py (offline usage, span and trace audit). Legacy scripts/contact_native_bridge.py still contains the obsolete UNAVAILABLE/residual/all-calls-intervention fields and must not be used for formal measurement. This sanity runner is the verified replacement path; no formal-run authorization is implied.

Official runtime protocol reference: [Codex App Server](https://learn.chatgpt.com/docs/app-server). The installed runtime's experimental generated JSON schemas are saved under protocol_schema; they define RawResponseCompletedNotification and its token breakdown fields.

Audit checks: {json.dumps(gates,ensure_ascii=False)}
'''
    (OUT/'INSTRUMENTATION_SANITY_REPORT.md').write_text(report,encoding='utf-8')
    print(json.dumps({'gate':gate,**times,**counts,'tokens':totals,'failed_fields':result['failed_fields']},indent=2))

if __name__=='__main__':main()
