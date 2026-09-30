"""Transport-neutral instruction envelope; execution policy belongs to runtime."""
from copy import deepcopy
from dataclasses import dataclass
from dex_hand.core.outcome import AdapterError, FailureClass as F

@dataclass(frozen=True)
class InstructionRequest:
    tool: str
    arguments: dict

    @classmethod
    def from_mapping(cls, value):
        if not isinstance(value,dict):
            raise ValueError("request must be a JSON object")
        unknown=set(value)-{"tool","arguments"}
        if unknown:
            raise AdapterError(F.NOT_SUPPORTED,"unsupported request fields: "+', '.join(sorted(unknown)))
        tool=value.get("tool")
        if not isinstance(tool,str) or not tool:
            raise ValueError("tool must be a nonempty string")
        args=value.get("arguments",{})
        if not isinstance(args,dict):
            raise ValueError("arguments must be a JSON object")
        return cls(tool,deepcopy(args))
