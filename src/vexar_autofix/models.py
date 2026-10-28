"""Data structures shared by the agent, the verifier, and the CLI."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Finding:
    """One diagnostic from the scanner, with a stable identity.

    `index` is part of the identity on purpose: two sinks of the same rule in one tool are
    two findings, and collapsing them would silently drop one from the work queue.
    """

    index: int
    rule_id: str
    message: str
    line: int
    tool_name: str | None
    severity: str

    @property
    def key(self) -> tuple[str, str, int, int]:
        return (self.rule_id, self.tool_name or "", self.line, self.index)


@dataclass
class Verdict:
    """A triage decision about one finding."""

    finding: Finding
    verdict: str  # "confirmed" | "mitigated" | "unclear"
    reason: str

    @property
    def confirmed(self) -> bool:
        return self.verdict == "confirmed"


@dataclass
class Edit:
    """One anchor replacement proposed by a model."""

    rule_id: str
    find: str
    replace: str
    why: str


@dataclass
class Attempt:
    """One patch attempt, kept in the report so a failure is always explainable."""

    number: int
    model_role: str
    edits: list[Edit] = field(default_factory=list)
    applied: int = 0
    failure: str | None = None
    accepted: bool = False

    def to_dict(self) -> dict[str, object]:
        """Flat, JSON-safe view. `__dict__` cannot be used: Edit is not serialisable, and
        the `--json` mode is the machine-readable artefact consumers actually parse."""
        return {
            "number": self.number,
            "model_role": self.model_role,
            "applied": self.applied,
            "failure": self.failure,
            "accepted": self.accepted,
            "edits": [
                {"rule_id": e.rule_id, "find": e.find, "replace": e.replace, "why": e.why} for e in self.edits
            ],
        }


@dataclass
class Verification:
    """The verifier's judgement on a patched working copy."""

    ok: bool
    cleared: list[str]
    remaining: list[str]
    new_findings: list[str]
    tests_ok: bool | None
    reason: str


@dataclass
class Usage:
    """Token and cost accounting, so a run can be priced rather than estimated."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    calls: int = 0
