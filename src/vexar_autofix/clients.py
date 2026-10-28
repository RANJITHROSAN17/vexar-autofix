"""Model clients.

Nebius Token Factory speaks the OpenAI Chat Completions wire format, so any OpenAI SDK
would work. This module uses stdlib `urllib` instead: the scanner the agent depends on is
dependency-free, and the agent should not be the thing that changes that.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any, ClassVar, Protocol

from .models import Usage

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"

# Token Factory serves the same catalogue from a global host and from region-suffixed
# hosts. Which one answers depends on the project's region, and the failure mode of
# picking wrong is a DNS error at demo time, so the preflight tries them all rather than
# trusting a single hardcoded value.
CANDIDATE_BASE_URLS: tuple[str, ...] = (
    "https://api.tokenfactory.nebius.com/v1",
    "https://api.tokenfactory.us-central1.nebius.com/v1",
    "https://api.tokenfactory.eu-north1.nebius.com/v1",
    "https://api.tokenfactory.us-north1.nebius.com/v1",
)

# Tiering is the point: each role does a different job, not the same job at a different
# price. Triage runs on every finding and only classifies; patching needs real code
# understanding; escalation is reserved for attempts that already failed verification.
MODEL_ROLES: dict[str, str] = {
    "triage": os.environ.get("AUTOFIX_MODEL_TRIAGE", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"),
    "patch": os.environ.get("AUTOFIX_MODEL_PATCH", "nvidia/nemotron-3-super-120b-a12b"),
    "escalate": os.environ.get("AUTOFIX_MODEL_ESCALATE", "nvidia/Nemotron-3-Ultra-550b-a55b"),
}

# List prices per 1M tokens, used only to report what a run cost.
MODEL_PRICES: dict[str, tuple[float, float]] = {
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": (0.06, 0.24),
    "nvidia/nemotron-3-super-120b-a12b": (0.30, 0.90),
    "nvidia/Nemotron-3-Ultra-550b-a55b": (1.00, 3.00),
}


class Client(Protocol):
    def complete(self, role: str, messages: Sequence[dict[str, str]], *, json_mode: bool = False) -> str: ...

    @property
    def usage(self) -> Usage: ...


def _record(usage: Usage, model: str, prompt_tokens: int, completion_tokens: int) -> None:
    usage.calls += 1
    usage.input_tokens += prompt_tokens
    usage.output_tokens += completion_tokens
    rate_in, rate_out = MODEL_PRICES.get(model, (0.0, 0.0))
    usage.cost_usd += (prompt_tokens * rate_in + completion_tokens * rate_out) / 1_000_000


class NebiusClient:
    """Token Factory client with bounded retries on transport errors."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 90.0,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise ValueError("an API key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._usage = Usage()

    @property
    def usage(self) -> Usage:
        return self._usage

    @property
    def base_url(self) -> str:
        return self._base_url

    def models(self) -> list[str]:
        """List the live catalogue.

        Worth calling once rather than trusting a hardcoded ID: Token Factory's lineup
        changes, and a stale model ID is the most common cause of a silent 404 at demo time.
        """
        request = urllib.request.Request(
            f"{self._base_url}/models",
            headers={"Authorization": f"Bearer {self._api_key}"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        return sorted(item["id"] for item in body.get("data", []))

    def complete(self, role: str, messages: Sequence[dict[str, str]], *, json_mode: bool = False) -> str:
        model = MODEL_ROLES[role]
        payload: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            # 0.0 so a judge re-running the demo reproduces the demo. At 0.1 the same
            # file produced 5 fixes in one run and 3 in the next, purely from sampling.
            "temperature": 0.0,
        }
        if json_mode:
            # Not every Nemotron deployment honours response_format, so callers parse
            # defensively and treat unparseable output as a failed attempt rather than
            # depending on this being enforced server-side.
            payload["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            request = urllib.request.Request(
                f"{self._base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self._timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
                usage = body.get("usage") or {}
                _record(
                    self._usage,
                    model,
                    int(usage.get("prompt_tokens", 0)),
                    int(usage.get("completion_tokens", 0)),
                )
                return str(body["choices"][0]["message"]["content"])
            except urllib.error.HTTPError as exc:
                # A 4xx means the request is wrong (bad model ID, bad key). Retrying it
                # just wastes the two days you have left.
                detail = exc.read().decode("utf-8", errors="replace")[:300]
                raise RuntimeError(f"Token Factory {exc.code} on model {model}: {detail}") from exc
            except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self._max_retries - 1:
                    time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Token Factory call failed after {self._max_retries} attempts: {last_error}")


class MockClient:
    """Offline rehearsal of the pipeline.

    Every edit it emits is fake and labelled as such. This is not a stand-in for
    evaluating model quality -- it exists so the control flow, the verifier, and the
    retry path are testable in CI without a key or a network.
    """

    # The fixture's two shell sinks collapse to one argv-form call. Written by hand and
    # replayed so the accept path, the score delta, and the diff are exercised too, not
    # only the rejection path.
    REHEARSAL_ACCEPT: ClassVar[tuple[str, str]] = (
        "    subprocess.run(cmd, shell=True, check=False)\n    os.system(cmd)\n",
        "    subprocess.run([cmd], check=False)  # argv form; no shell, no eval\n",
    )

    def __init__(self, fail_first_patch: bool = False, rehearse_accept: bool = False) -> None:
        self._usage = Usage()
        self._fail_first = fail_first_patch
        self._rehearse_accept = rehearse_accept
        self._patch_attempts = 0

    @property
    def usage(self) -> Usage:
        return self._usage

    def complete(self, role: str, messages: Sequence[dict[str, str]], *, json_mode: bool = False) -> str:
        self._usage.calls += 1
        payload = json.loads(messages[-1]["content"])

        if role == "triage":
            from .verifier import AUTOFIXABLE

            return json.dumps(
                {
                    "verdicts": [
                        {
                            "index": f["index"],
                            "rule_id": f["rule_id"],
                            "verdict": "confirmed" if f["rule_id"] in AUTOFIXABLE else "unclear",
                            "reason": "rehearsal verdict: rule matches a known-sink pattern",
                        }
                        for f in payload["findings"]
                    ]
                }
            )

        self._patch_attempts += 1
        if self._fail_first and self._patch_attempts == 1:
            return json.dumps(
                {
                    "edits": [],
                    "note": "rehearsal: deliberately empty patch to force a rejection",
                }
            )
        if self._rehearse_accept:
            find, replace = self.REHEARSAL_ACCEPT
            return json.dumps(
                {
                    "edits": [
                        {
                            "rule_id": "MCP005",
                            "find": find,
                            "replace": replace,
                            "why": "rehearsal: argv form removes both shell sinks",
                        }
                    ]
                }
            )
        return json.dumps({"edits": [], "note": "rehearsal: no edits emitted"})
