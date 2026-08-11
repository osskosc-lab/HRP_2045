from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

EpistemicStatus = Literal["observed", "inferred", "unknown"]


@dataclass
class AgentDescriptor:
    agent_id: str
    implementation: str
    version: str = "unknown"
    capabilities: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    memory_mode: str = "unspecified"
    modalities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Challenge:
    challenge_id: str
    kind: str
    prompt: str
    payload: dict[str, Any]
    required_properties: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentResponse:
    challenge_id: str
    answer: Any = None
    epistemic_status: EpistemicStatus = "unknown"
    confidence: float = 0.0
    provenance: list[str] = field(default_factory=list)
    requested_action: str | None = None
    action_authorized: bool | None = None
    disagreement: str | None = None
    update_after_counterevidence: bool | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CheckResult:
    challenge_id: str
    passed: bool
    score: float
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationReport:
    passed: bool
    score: float
    threshold: float
    checks: list[CheckResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "threshold": self.threshold,
            "checks": [c.to_dict() for c in self.checks],
        }
