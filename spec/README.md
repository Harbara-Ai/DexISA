# ISA specification status

The machine-readable MAKE_CONTACT schema is the current implemented public argument contract, not an extract of the old v0.2 draft. It includes only object_id, contact_groups and termination (contact_present/contact_dwell); generic Agent-visible constraints are intentionally deferred.

| File | Status |
| --- | --- |
| [instructions/make_contact.schema.json](instructions/make_contact.schema.json) | Canonical implemented MAKE_CONTACT arguments; matches Runtime validation |
| [instructions/break_contact.schema.json](instructions/break_contact.schema.json) | Historical broader draft extract; not a parameterized implemented BREAK_CONTACT API |
| [v0.2 Markdown](../dexterous-hand-skill-mcp-spec-v0.2.md) | Broader design draft / historical semantic reference; not fully equivalent to current callable APIs |

The draft taxonomy (including persistent MAINTAIN_GRASP), ContactState, VirtualContactGroup, ConstraintAllocation, TerminationSemantics, FailureClass, SkillOutcome, Capability and belief/uncertainty concepts are preserved. The draft's packaged Markdown copy still validates existing result shapes. Its input defaults do not override reference controllers.

Edit the canonical MAKE_CONTACT file, then run `python scripts/extract_instruction_schemas.py` to sync the packaged mirror. `--check` verifies byte equality and checks the separate BREAK_CONTACT draft extraction. Runtime loads dex_hand/schema/make_contact.schema.json through importlib.resources; its accepted argument keys come from this schema. Generation no longer replaces MAKE_CONTACT with an old draft extract.

Current examples, omissions, dynamic availability checks and failure handling: [docs/MAKE_CONTACT_INTERFACE.md](../docs/MAKE_CONTACT_INTERFACE.md). Ownership and dependency injection: [ARCHITECTURE.md](../ARCHITECTURE.md). Other instruction parameterization is deferred.
