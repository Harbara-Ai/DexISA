from dataclasses import dataclass, field, asdict
from enum import StrEnum


class FailureClass(StrEnum):
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    UNREACHABLE = "UNREACHABLE"
    NO_CONTACT_FOUND = "NO_CONTACT_FOUND"
    PREMATURE_CONTACT = "PREMATURE_CONTACT"
    INCOMPLETE_CONTACT_SET = "INCOMPLETE_CONTACT_SET"
    CONTACT_LOST = "CONTACT_LOST"
    OBJECT_DISPLACED = "OBJECT_DISPLACED"
    OBJECT_DROPPED = "OBJECT_DROPPED"
    SLIP_UNRECOVERABLE = "SLIP_UNRECOVERABLE"
    JAMMED = "JAMMED"
    ACTUATOR_LIMIT = "ACTUATOR_LIMIT"
    TIMEOUT = "TIMEOUT"
    COLLISION = "COLLISION"
    WRENCH_LIMIT_EXCEEDED = "WRENCH_LIMIT_EXCEEDED"
    SENSOR_UNAVAILABLE = "SENSOR_UNAVAILABLE"


@dataclass
class SkillOutcome:
    status: str
    skill: str
    failure_class: FailureClass | None = None
    failure_detail: str = ""
    achieved_state: dict = field(default_factory=dict)
    residual_uncertainty: list[str] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.status == "SUCCEEDED": self.status = "SUCCESS"
        if self.status not in ("SUCCESS", "FAILED"):
            raise ValueError("invalid status")
        if (self.status == "FAILED") != (self.failure_class is not None):
            raise ValueError("FAILED requires failure_class; SUCCEEDED forbids it")

    @property
    def success(self):
        return self.status == "SUCCESS"

    def to_dict(self):
        return asdict(self)

    def to_v02(self):
        """Strict draft wire shape; richer local experiment state remains diagnostic."""
        result = {"status": self.status, "skill": self.skill,
                  "achieved": {"duration_s": self.diagnostics.get("execution_time_s", 0.)},
                  "residual_uncertainty": [{"field": x.split()[0], "note": x} for x in self.residual_uncertainty],
                  "adapter_diagnostics": {**self.diagnostics, "achieved_state": self.achieved_state}}
        if self.failure_class:
            result.update(failure_class=self.failure_class, failure_detail=self.failure_detail)
        return result


class AdapterError(RuntimeError):
    def __init__(self, failure_class, detail):
        super().__init__(detail)
        self.failure_class = failure_class
