"""Authoritative provider usage; subset counters are never double counted."""
def parse_usage(response):
    u=response.get('usage')
    if not isinstance(u,dict) or any(not isinstance(u.get(k),int) for k in ('input_tokens','output_tokens','total_tokens')):
        raise ValueError('M3 unavailable: response did not contain authoritative API usage')
    return {'input_tokens':u['input_tokens'],'output_tokens':u['output_tokens'],'total_tokens':u['total_tokens'],
        'cached_input_tokens':u.get('input_tokens_details',{}).get('cached_tokens'),
        'reasoning_tokens':u.get('output_tokens_details',{}).get('reasoning_tokens')}
