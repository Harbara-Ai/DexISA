"""Verify published hashes and native measurement arithmetic without model/simulation calls."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def rows(p):return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines()]
manifest=load(ROOT/'PUBLICATION_MANIFEST.json')
for item in manifest['files']:
    assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['published_sha256'],item['path']
for folder,name in [('results_instrumentation_sanity','instrumentation_sanity_result.json'),('results_wuji_contact_direct_single','wuji_contact_direct_single.json')]:
    p=ROOT/folder;r=load(p/name);turns=load(p/'token_usage_per_turn.json')
    raw=[x['message']['params'] for x in rows(p/'episode_native_events.jsonl') if x['message'].get('method')=='rawResponse/completed']
    assert r['formal'] is False and r['resolved_model']=='gpt-5.6-luna' and r['reasoning_effort']=='low'
    assert len(raw)==len(turns)==r['N_decision_cycles']
    for snake,camel in [('input_tokens','inputTokens'),('output_tokens','outputTokens'),('cached_input_tokens','cachedInputTokens'),('reasoning_output_tokens','reasoningOutputTokens')]:
        assert sum(t[snake] for t in turns)==sum(t['usage'][camel] for t in raw)==r['token_usage'][snake]
    assert r['token_usage']['total_tokens']==r['token_usage']['input_tokens']+r['token_usage']['output_tokens']
    trace=rows(p/'tool_trace.jsonl')
    assert len(trace)==r['N_tool_calls']
    assert sum(t['tool'] in ['MAKE_CONTACT','set_joint_targets','stop'] for t in trace)==r['N_control_interventions']
    frames=sum(1 for _ in (p/'physical/episode_simulation.jsonl').open(encoding='utf-8'))
    assert abs(frames*.002-r['T_physical'])<1e-8
    spans={s['spanId']:s for row in rows(p/'episode_otel.jsonl') for rs in row['data']['resourceSpans'] for sc in rs['scopeSpans'] for s in sc['spans']}
    decisions=rows(p/'decision_trace.jsonl')
    for d in decisions:
        s=spans[d['span_id']]
        assert int(s['startTimeUnixNano'])==d['request_start']['unix_ns']
        assert int(s['endTimeUnixNano'])==d['response_end']['unix_ns']
    assert abs(sum(d['duration_s'] for d in decisions)-r['T_agent'])<1e-8
    print(folder+': PASS (native usage, timing, interventions, simulation)')
assert load(ROOT/'results_instrumentation_sanity/prepared_initial_state.json')==load(ROOT/'results_wuji_contact_direct_single/prepared_initial_state.json')
print('Publication manifest and paired initial-state equivalence: PASS')
