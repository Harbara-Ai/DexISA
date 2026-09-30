# ISA specification

The [v0.2 normative Markdown](../dexterous-hand-skill-mcp-spec-v0.2.md) remains the semantic baseline. It defines SHAPE_HAND, MAKE_CONTACT, ESTABLISH_GRASP, MANIPULATE_IN_CONTACT, CHANGE_CONTACTS, APPLY_WRENCH, FOLLOW_CONSTRAINT, BREAK_CONTACT, PROBE_INTERACTION and persistent MAINTAIN_GRASP.

ContactState, VirtualContactGroup, ConstraintAllocation, TerminationSemantics, CanonicalObservation, FailureClass, SkillOutcome, Capability and belief/uncertainty remain in that document. The packaged copy in dex_hand/schema supports installed outcome validation and is checked for byte equality.

instructions/make_contact.schema.json and break_contact.schema.json are exact Draft 2020-12 input-schema extracts including referenced shared types. They preserve draft defaults, rather than silently replacing reference-controller defaults. Reproduce/check with `python scripts/extract_instruction_schemas.py [--check]`. Other schemas are not migrated in Phase 1.

The implemented JSONL subset is documented separately in [docs/MAKE_CONTACT_INTERFACE.md](../docs/MAKE_CONTACT_INTERFACE.md). Its scene group IDs and constraints/termination envelope are an incremental reference pilot, not the full normative wire schema.

See [ARCHITECTURE.md](../ARCHITECTURE.md) for parameter ownership and [PARAMETER_CLASSIFICATION.md](../PARAMETER_CLASSIFICATION.md) for the current execution signatures.
