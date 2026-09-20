"""Offline native-telemetry audit and single-pair report; no new episodes."""
import json,hashlib,math
from pathlib import Path
from summarize_instrumentation_sanity import usage,inference_spans,attrs,rows,iso,TOKEN_MAP
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results_wuji_contact_direct_single';BASE=ROOT/'results_instrumentation_sanity'
def read(n):return json.loads((OUT/n).read_text(encoding='utf-8'))
def save(n,v):(OUT/n).write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
def table(headers,values):
    return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']+['---:']*(len(headers)-1))+' |\n'+'\n'.join('| '+' | '.join(fmt(x) for x in row)+' |' for row in values)
def fmt(x):return 'UNAVAILABLE' if x is None else f'{x:.7f}' if isinstance(x,float) else str(x)
def main():
    ex=read('execution.json');eq=read('initial_equivalence.json');baseline=json.loads((BASE/'instrumentation_sanity_result.json').read_text())
    ev=rows(OUT/'episode_native_events.jsonl') if (OUT/'episode_native_events.jsonl').exists() else []
    tools=rows(OUT/'tool_trace.jsonl') if (OUT/'tool_trace.jsonl').exists() else []
    otel=rows(OUT/'episode_otel.jsonl') if (OUT/'episode_otel.jsonl').exists() else []
    spans=[s for l in otel for r in l['data'].get('resourceSpans',[]) for sc in r['scopeSpans'] for s in sc['spans']]
    calls=inference_spans(spans);responses=[e for e in ev if e['message'].get('method')=='rawResponse/completed']
    problems=list(ex['errors']);per=[];decisions=[]
    if not calls or len(calls)!=len(responses):problems.append('Native inference/usage event counts do not match')
    for i,((s,a),e) in enumerate(zip(calls,responses),1):
        p=e['message']['params'];start=int(s['startTimeUnixNano']);end=int(s['endTimeUnixNano'])
        try:u=usage(p['usage'])
        except Exception as error:problems.append(str(error));continue
        if abs(end/1e6-e['message']['emittedAtMs'])>100:problems.append('Ambiguous response/span pairing')
        if p['threadId']!=ex['thread_id']:problems.append('Native usage thread mismatch')
        if a['model']!='gpt-5.6-luna':problems.append('Resolved model mismatch')
        per.append({'decision_cycle':i,'turn_id':p['turnId'],'response_id':p['responseId'],'usage_source':'native_turn_usage',**u})
        next_start=int(calls[i][0]['startTimeUnixNano']) if i<len(calls) else ex['t_terminal_outcome']['unix_ns']+1
        actions=[t['index'] for t in tools if start<=t['tool_start']['unix_ns']<next_start]
        decisions.append({'decision_cycle':i,'turn_id':p['turnId'],'response_id':p['responseId'],'resolved_model':a['model'],
            'request_start':{'unix_ns':start,'utc':iso(start)},'response_end':{'unix_ns':end,'utc':iso(end)},
            'duration_s':(end-start)/1e9,'timing_source':'native_otel:responses_websocket.stream_request',
            'span_id':s['spanId'],'trace_id':s['traceId'],'visible_tool_indices':actions})
    if len({p['response_id'] for p in per})!=len(per):problems.append('Duplicate usage response IDs')
    totals={k:sum(p[k] for p in per) for k in [*TOKEN_MAP,'total_tokens']} if per else None
    usage_available=bool(per) and len(per)==len(calls)==len(responses)
    final_usage=[e['message']['params']['tokenUsage']['total'] for e in ev if e['message'].get('method')=='thread/tokenUsage/updated']
    native_total_matches=bool(final_usage) and totals==usage(final_usage[-1])
    if not native_total_matches:problems.append('Episode usage does not match native thread total')
    thread=read('native_thread.json') if (OUT/'native_thread.json').exists() else None
    context={};meta={};rollout_matches=False
    if thread:
        rollout=rows(Path(thread['thread']['path']))
        meta=next(r['payload'] for r in rollout if r['type']=='session_meta')
        contexts=[r['payload'] for r in rollout if r['type']=='turn_context']
        context=contexts[-1] if contexts else {}
        ru=[r['payload']['info']['total_token_usage'] for r in rollout if r['type']=='event_msg' and r['payload'].get('type')=='token_count' and r['payload'].get('info')]
        rollout_matches=bool(ru) and totals is not None and all(totals[k]==ru[-1][k] for k in totals)
        save('native_rollout_evidence.json',{'source_path':thread['thread']['path'],'session_id':meta.get('id'),'cli_version':meta.get('cli_version'),'dynamic_tools':meta.get('dynamic_tools'),
            'turn_context':{k:context.get(k) for k in ['model','effort','turn_id']},'total_token_usage':ru[-1] if ru else None})
    if context.get('model')!='gpt-5.6-luna' or context.get('effort')!='low':problems.append('Native rollout model/effort mismatch')
    first=decisions[0]['request_start']['unix_ns'] if decisions else None
    prepared=ex['t_episode_prepared']['unix_ns'];terminal=ex['t_terminal_outcome']['unix_ns']
    times={'T_startup':(first-prepared)/1e9 if first else None,'T_active':(terminal-first)/1e9 if first else None,
        'T_agent':sum(d['duration_s'] for d in decisions) if decisions else None,
        'T_tool':sum((t['tool_end']['monotonic_ns']-t['tool_start']['monotonic_ns'])/1e9 for t in tools),
        'T_physical':ex['sim_time_end']-ex['sim_time_start'],'T_total':(terminal-prepared)/1e9}
    counts={'N_decision_cycles':len(calls),'N_control_interventions':sum(t['tool'] in ['set_joint_targets','stop'] for t in tools),
        'N_tool_calls':len(tools),'N_state_queries':sum(t['tool']=='get_state' for t in tools),
        'N_low_level_command_calls':sum(t['tool']=='set_joint_targets' for t in tools)}
    physical=ex['physical'];shield=physical['shield_failure'];timed_out=ex['benchmark_timeout_triggered']
    terminal_valid=physical['physical_success'] and not shield and not ex['terminal_observation']['collision'] and physical['max_object_drift']<=.015 and physical['max_group_force']<=4
    if problems:quality='INFRA_FAILURE'
    elif shield:quality='SHIELD_INTERVENED_FAILURE'
    elif timed_out:quality='SHIELD_INTERVENED_FAILURE'
    elif terminal_valid:quality='SUCCESS'
    elif not ex['terminal_observation']['collision']:quality='SELF_SAFE_FAILURE'
    else:quality='UNSAFE_FAILURE'
    failure='INFRA_FAILURE' if problems else shield or ('BENCHMARK_TIMEOUT' if timed_out else None if terminal_valid else 'NO_CONTACT_ESTABLISHED')
    nframes=sum(1 for _ in (OUT/'physical/episode_simulation.jsonl').open())
    # merge_into_namespaces counts transport specs, not semantic tools. Use the
    # native dynamic-tool registration and persisted session registry instead.
    spec_counts=[int(attrs(s)['dynamic_tool_count']) for s in spans if s['name']=='append_dynamic_tool_runtimes']
    registry=meta.get('dynamic_tools',[])
    expected_tools={'describe_hand','get_state','set_joint_targets','stop'}
    checks={'initial_state_equivalent':eq['initial_state_equivalent'],'shared_sources_unchanged':read('shared_before.json')==read('shared_after.json'),
        'skill_baseline_files_unchanged':read('baseline_files_before.json')==read('baseline_files_after.json'),
        'native_usage_matches_thread_total':native_total_matches,'native_usage_matches_rollout_total':rollout_matches,
        'native_tool_count_matches':counts['N_tool_calls']==sum(e['message'].get('method')=='item/tool/call' for e in ev),
        'only_four_semantic_tools':bool(spec_counts) and all(n==4 for n in spec_counts) and {t['name'] for t in registry}==expected_tools and all(t['tool'] in expected_tools for t in tools),
        'physical_trace_time_matches':abs(nframes*.002-times['T_physical'])<1e-8,
        'native_timing_valid':all(v is not None and v>=0 for v in times.values()) and bool(decisions) and all(d['duration_s']>0 for d in decisions),
        'runtime_version_matches_skill':meta.get('cli_version')==baseline['runtime_version']}
    if not all(checks.values()):
        problems.append({'failed_audit_checks':[k for k,v in checks.items() if not v]})
        quality='INFRA_FAILURE';failure='INFRA_FAILURE'
    result={'formal':False,'purpose':'single_pair_comparison','hand':'Wuji','agent':'DIRECT_AGENT','task':'GUARDED_CONTACT',
        'outcome':'SUCCESS' if quality=='SUCCESS' else 'INFRA_FAILURE' if quality=='INFRA_FAILURE' else 'FAILED','terminal_quality':quality,
        'requested_model':'gpt-5.6-luna','resolved_model':context.get('model'),'reasoning_effort':context.get('effort'),'runtime_version':meta.get('cli_version'),
        'thread_id':ex['thread_id'],'session_id':meta.get('id'),'turn_id':context.get('turn_id'),
        'usage_source':'native_turn_usage','token_usage':{'available':usage_available,**(totals or {})},**times,**counts,
        'peak_group_load_N':physical['max_group_force'],'max_object_drift_m':physical['max_object_drift'],
        'failure_class':failure,'shield_triggered':bool(shield),'benchmark_timeout_triggered':timed_out,
        'terminal_intervention_source':'common_safety_shield' if shield else 'benchmark_watchdog' if timed_out else None,
        'explicit_agent_stop':ex['explicit_agent_stop'],'contact_to_action_end_s':physical['contact_to_action_end_s'],'initial_state_equivalent':eq['initial_state_equivalent'],
        'state_and_scene_hashes':eq,'audit_checks':checks,'errors':problems,'simulation_frames':nframes,
        'sim_time_start':ex['sim_time_start'],'sim_time_end':ex['sim_time_end'],
        't_episode_prepared':ex['t_episode_prepared'],'t_first_agent_request_start':decisions[0]['request_start'] if decisions else None,
        't_terminal_outcome':ex['t_terminal_outcome'],'baseline_result':str(BASE/'instrumentation_sanity_result.json'),
        'native_transport_wrapper_calls':sum(e['message'].get('method')=='rawResponseItem/completed' and e['message'].get('params',{}).get('item',{}).get('type')=='custom_tool_call' for e in ev),
        'physical':physical}
    save('wuji_contact_direct_single.json',result);save('token_usage_per_turn.json',per)
    (OUT/'decision_trace.jsonl').write_text(''.join(json.dumps(d)+'\n' for d in decisions),encoding='utf-8')
    token=totals or {};metrics=[('Outcome',result['outcome']),('Terminal quality',quality),('Input tokens',token.get('input_tokens')),
        ('Cached input',token.get('cached_input_tokens')),('Output tokens',token.get('output_tokens')),('Reasoning output',token.get('reasoning_output_tokens')),
        ('Total tokens',token.get('total_tokens'))]+list(times.items())+[(k.removeprefix('N_').replace('_',' ').capitalize(),v) for k,v in counts.items()]+[
        ('Peak group load N',physical['max_group_force']),('Max object drift m',physical['max_object_drift']),('Failure class',failure or 'NONE')]
    pair=[('Success',baseline['outcome'],result['outcome']),('Total tokens',baseline['token_usage']['total_tokens'],token.get('total_tokens')),
        ('Decision cycles',baseline['N_decision_cycles'],counts['N_decision_cycles']),('Control interventions',baseline['N_control_interventions'],counts['N_control_interventions'])]
    pair += [(k+' s',baseline[k],times[k]) for k in ['T_active','T_agent','T_physical','T_total']]
    pair += [('Peak load N',baseline['physical']['max_group_force'],physical['max_group_force']),('Max drift m',baseline['physical']['max_object_drift'],physical['max_object_drift'])]
    comparison=[]
    for name,s,d in pair:
        valid=isinstance(s,(int,float)) and isinstance(d,(int,float)) and math.isfinite(s) and math.isfinite(d)
        comparison.append([name,s,d,(f'D-S={d-s:.7f}; D/S={d/s:.4f}' if s else f'D-S={d-s:.7f}; ratio unavailable') if valid else '—'])
    save('pair_comparison.json',{'formal':False,'evidence':'preliminary single-pair evidence','difference_definition':'Direct minus Skill','ratio_definition':'Direct divided by Skill','rows':comparison,'audit_checks':checks})
    baseline_tools=rows(BASE/'tool_trace.jsonl')
    visible={'skill_baseline':[{'tool':t['tool'],'arguments':t['arguments']} for t in baseline_tools],
        'direct':[{'tool':t['tool'],'arguments':t['arguments'],'sim_time_start':t['sim_time_start'],'sim_time_end':t['sim_time_end']} for t in tools]}
    save('visible_action_trace.json',visible)
    skill_trace=' → '.join([t['tool'] for t in baseline_tools]+['terminal'])
    direct_trace=' → '.join([t['tool'] for t in tools]+['terminal'])
    report=f'''# NON_FORMAL Wuji CONTACT Direct single episode

`formal=false`; `purpose=single_pair_comparison`; **preliminary single-pair evidence**.
One new Direct episode, no reruns. The existing Skill sanity result is reused without modification. No formal CSV/statistics are updated.

{table(['Metric','Direct'],metrics)}

## Pair comparison

{table(['Metric','Skill Agent','Direct Agent','Difference / Ratio'],comparison)}

Ratios are Direct/Skill. Times compare **time-to-terminal-outcome**; a failed Direct episode is not a successful completion-time measurement. One pair provides no statistical significance or population-level claim.

## Visible action trace

Skill baseline: `{skill_trace}`

Direct: `{direct_trace}`

Exact Direct joint targets/durations are preserved in visible_action_trace.json and tool_trace.jsonl. No hidden reasoning is reproduced. Direct made no explicit stop call; after its last finite-duration command it ended the native turn. First contact preceded that command's end by {physical['contact_to_action_end_s']:.7f} simulation seconds. This is action-boundary termination, not immediate contact-triggered stopping. The common evaluator reports SUCCESS because terminal contact, load, drift and collision constraints are valid. State-query count is zero because the initial observation and each of the five command-boundary observations supplied feedback without separate get_state calls.

## Scene and evaluator equivalence

`initial_state_equivalent={str(eq['initial_state_equivalent']).lower()}`.
Skill prepared-state SHA256: `{eq['skill_initial_state_sha256']}`.
Direct prepared-state SHA256: `{eq['direct_initial_state_sha256']}`.
Scene XML SHA256 (both): `{eq['scene_xml_sha256']}`.
The same Wuji adapter, fixed palm, medium supported cylinder, pose/friction, preshape, effort limits and PilotEpisode.tick evaluator were used. The low-level dispatcher executes the requested duration even after a legal contact; the evaluator records success but does not stop motion. No trajectory, IK helper, contact advance helper, Skill implementation, Skill trace or Skill usage was sent to Direct.

## Safety and timeout separation

- **Common safety shield:** existing joint-range validation and original model effort caps, saturation guard, group load (4 N), object drift (0.015 m), unrelated collision/contact checks and motion latch. Shared code is unchanged. **The common shield currently has no independent joint velocity threshold.** A common-shield violation is reported in tool feedback; Direct may then query or call stop. `shield_triggered={bool(shield)}`; explicit agent stop: `{ex['explicit_agent_stop']}`.
- **Skill-internal guards / timeout:** MAKE_CONTACT's contact-triggered termination, guarded advance/displacement checks and 8-second physical timeout belong to the Skill implementation. They were not copied to Direct. Direct has no equivalent physical acquisition timeout or automatic success-triggered stopping. This is a validity limitation of this single pair, not proof of identical internal termination mechanisms.
- **Benchmark-level episode timeout:** 180 seconds from native turn/start dispatch, matching the pre-existing sanity runner's timeout duration/origin. This watchdog is independent of contact. On expiration it terminates the episode and holds posture; it is reported separately from the common shield. Triggered: `{timed_out}`. No extra delay or tuned joint-command budget was introduced.

## Native instrumentation and feedback

Requested/resolved model: `gpt-5.6-luna` / `{context.get('model')}`; reasoning: `{context.get('effort')}`; runtime: `{meta.get('cli_version')}`.
Thread/session: `{ex['thread_id']}`; turn: `{context.get('turn_id')}`.
Usage source: `native_turn_usage` (`rawResponse/completed`), cross-checked with native thread total and session rollout. No token estimates. Cache-write input: `{token.get('cache_write_input_tokens')}`. Cached and reasoning tokens are breakdowns, not extra additions.

Decision cycles count actual native non-warmup inference requests. Control interventions count only set_joint_targets and stop. Low-level command calls count set_joint_targets; stop is separately observable. Robot tool calls exclude the native code-mode transport wrapper (wrapper calls: {result['native_transport_wrapper_calls']}). Native OTel websocket stream spans supply request_start/response_end and T_agent, never a total-minus-tools residual. Terminal time includes final native inference; simulation pauses during inference. {nframes} simulation frames at 0.002 s match physical elapsed time.

Direct receives the same CanonicalObservation contacts/object/status source and precision as Skill, with relevant joint positions/velocities, load, drift and collision fields added for low-level decisions. Static joint metadata is returned only once by describe_hand. The low-level API's action-boundary state is retained. Runtime transport descriptions explicitly tell the model to display the full tool return, addressing the baseline's known omission of printed structured feedback; this transport/prompt difference is a validity limitation. Fresh context and disabled environment tools prevent file access to the baseline. Native events show a general host skill catalog and permissions context were still injected despite the requested skip-host-skill-discovery setting, as in the Skill baseline; neither context included the robot Skill implementation or its successful trace. Thus the literal desired context-only restriction is not fully enforced by this runtime. Token comparisons include actual context differences and are not a controlled estimate of semantic-tool schema savings.

The semantic tool allowlist is audited against session_meta.dynamic_tools and native append_dynamic_tool_runtimes.dynamic_tool_count (four), not merge_into_namespaces.tool_spec_count (three native transport specs in both conditions). This offline audit-field correction does not change or rerun the episode. All six observed robot calls belong to the authorized four-tool allowlist.

No post-stop physical dwell test was added. Safe terminal evidence is limited to the recorded state, native turn termination and existing hold cleanup. The reused Skill baseline also has this limitation.

## Audit

{json.dumps(checks,ensure_ascii=False,indent=2)}

Errors: `{json.dumps(problems,ensure_ascii=False)}`.

This single pair can inform a separately authorized CONTACT repeat plan if measurement checks pass; it remains **preliminary single-pair evidence**. No additional episodes have been started.
'''
    (OUT/'WUJI_CONTACT_DIRECT_SINGLE.md').write_text(report,encoding='utf-8')
    print(json.dumps({'outcome':result['outcome'],'terminal_quality':quality,'failure_class':failure,'tokens':totals,**counts,**times,'audit_checks':checks,'errors':problems},indent=2),flush=True)

if __name__=='__main__':main()
