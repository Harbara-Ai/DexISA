"""Sync implemented MAKE_CONTACT packaging and reproduce the BREAK_CONTACT draft extract."""
import argparse
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]

def extracts():
    text=(ROOT/'dexterous-hand-skill-mcp-spec-v0.2.md').read_text(encoding='utf-8')
    blocks=[json.loads(b) for b in re.findall(r"```json\s*\n(.*?)\n```",text,re.S)]
    shared=next(b['$defs'] for b in blocks if '$defs' in b and 'SkillOutcome' in b['$defs'])
    result={"make_contact":json.loads((ROOT/"spec/instructions/make_contact.schema.json").read_text(encoding="utf-8"))}
    for name in ('break_contact',):
        item=next(b for b in blocks if b.get('name')=='robot.skill.'+name)
        schema={'$schema':'https://json-schema.org/draft/2020-12/schema',**item['inputSchema']}
        pending=[schema];needed={}
        while pending:
            node=pending.pop()
            if isinstance(node,dict):
                ref=node.get('$ref','')
                if ref.startswith('#/$defs/'):
                    key=ref.split('/')[-1]
                    if key not in needed:
                        needed[key]=shared[key];pending.append(shared[key])
                pending.extend(node.values())
            elif isinstance(node,list):pending.extend(node)
        if needed:schema['$defs']=needed
        result[name]=schema
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    for name,schema in extracts().items():
        path=ROOT/'spec/instructions'/(name+'.schema.json')
        if args.check:
            if json.loads(path.read_text(encoding='utf-8'))!=schema:
                raise SystemExit('Extract differs from normative source: '+str(path))
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    canonical=ROOT/'spec/instructions/make_contact.schema.json'
    packaged=ROOT/'dex_hand/schema/make_contact.schema.json'
    if args.check:
        if canonical.read_bytes()!=packaged.read_bytes():
            raise SystemExit('Packaged MAKE_CONTACT differs from canonical implemented schema')
    else:
        packaged.write_bytes(canonical.read_bytes())
    print('Implemented MAKE_CONTACT mirror and BREAK_CONTACT draft verified.' if args.check else 'Implemented MAKE_CONTACT mirror synced; BREAK_CONTACT draft extracted.')

if __name__=='__main__':main()
