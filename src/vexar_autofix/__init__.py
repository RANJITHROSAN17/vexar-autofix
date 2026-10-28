"""vexar-autofix -- an MCP security agent that can prove it fixed your code."""

from __future__ import annotations

__version__ = "0.1.0"

from .agent import autofix, propose, triage
from .clients import DEFAULT_BASE_URL, MODEL_ROLES, MockClient, NebiusClient
from .models import Attempt, Edit, Finding, Usage, Verdict, Verification
from .verifier import AUTOFIXABLE, apply_edits, build_diff, run_tests, scan, score_of, verify

__all__ = [
    "AUTOFIXABLE",
    "DEFAULT_BASE_URL",
    "MODEL_ROLES",
    "Attempt",
    "Edit",
    "Finding",
    "MockClient",
    "NebiusClient",
    "Usage",
    "Verdict",
    "Verification",
    "__version__",
    "apply_edits",
    "autofix",
    "build_diff",
    "propose",
    "run_tests",
    "scan",
    "score_of",
    "triage",
    "verify",
]
