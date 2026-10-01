"""Packaged mirror of the implemented instruction schema; no draft extraction."""
import json
from importlib.resources import files
from jsonschema import Draft202012Validator

MAKE_CONTACT_SCHEMA = json.loads(
    files("dex_hand").joinpath("schema/make_contact.schema.json").read_text(encoding="utf-8")
)
Draft202012Validator.check_schema(MAKE_CONTACT_SCHEMA)
MAKE_CONTACT_VALIDATOR = Draft202012Validator(MAKE_CONTACT_SCHEMA)
