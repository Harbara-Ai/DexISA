import json
import re
from importlib.resources import files
from jsonschema import Draft202012Validator


def spec_schema():
    source = files("dex_hand").joinpath("schema/dexterous-hand-skill-mcp-spec-v0.2.md")
    for block in re.findall(r"```json\s*\n(.*?)\n```", source.read_text(encoding="utf-8"), re.S):
        doc=json.loads(block)
        if "$defs" in doc and "SkillOutcome" in doc["$defs"]:
            return {"$schema":"https://json-schema.org/draft/2020-12/schema", "$defs":doc["$defs"], "$ref":"#/$defs/SkillOutcome"}
    raise ValueError("SkillOutcome definitions missing from source specification")


def validate_outcome(outcome):
    schema=spec_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(outcome.to_v02())
