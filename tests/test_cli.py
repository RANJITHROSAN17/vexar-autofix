"""Preflight tests.

The preflight exists because a wrong key and a wrong region both surface as a confusing
error mid-run. These tests pin that each failure is turned into a specific, actionable
message -- that is the whole value of the command.
"""

from __future__ import annotations

import urllib.error

import pytest

from vexar_autofix.cli import main
from vexar_autofix.clients import DEFAULT_BASE_URL, MODEL_ROLES, NebiusClient


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.test", code, "err", {}, None)  # type: ignore[arg-type]


class TestPreflight:
    def test_missing_key_points_at_where_to_get_one(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
        assert main(["--preflight"]) == 2
        assert "tokenfactory.nebius.com" in capsys.readouterr().err

    def test_live_models_are_used_when_the_key_works(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("NEBIUS_API_KEY", "key")
        monkeypatch.setattr(NebiusClient, "models", lambda self: list(MODEL_ROLES.values()))
        assert main(["--preflight"]) == 0
        assert "ready:" in capsys.readouterr().out

    def test_rejected_key_is_explained_not_just_reported(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("NEBIUS_API_KEY", "key")

        def reject(self: NebiusClient) -> list[str]:
            raise http_error(401)

        monkeypatch.setattr(NebiusClient, "models", reject)
        assert main(["--preflight"]) == 3
        err = capsys.readouterr().err
        assert "No endpoint accepted the key" in err
        assert "AI Cloud / service-account key" in err, "the most likely cause must be named"

    def test_a_missing_routed_model_names_the_override_variable(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Silent 404s at demo time come from stale model IDs, so the command must complain
        # and tell you exactly which env var to set.
        monkeypatch.setenv("NEBIUS_API_KEY", "key")
        monkeypatch.setattr(NebiusClient, "models", lambda self: ["some/other-model"])
        assert main(["--preflight"]) == 1
        err = capsys.readouterr().err
        assert "AUTOFIX_MODEL_TRIAGE" in err
        assert "some/other-model" in err, "the replacement must be listed, not just demanded"

    def test_a_region_specific_endpoint_is_echoed_back_for_export(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Working out of region means every later run needs the base URL too; printing the
        # export line is what stops that being rediscovered later.
        monkeypatch.setenv("NEBIUS_API_KEY", "key")
        monkeypatch.delenv("NEBIUS_BASE_URL", raising=False)

        def only_from_region(self: NebiusClient) -> list[str]:
            if self.base_url == DEFAULT_BASE_URL:
                raise urllib.error.URLError("global host does not serve this project")
            return list(MODEL_ROLES.values())

        monkeypatch.setattr(NebiusClient, "models", only_from_region)
        assert main(["--preflight"]) == 0
        captured = capsys.readouterr()
        assert "export NEBIUS_BASE_URL=" in captured.err

    def test_target_is_not_required_for_preflight_but_required_otherwise(self) -> None:
        with pytest.raises(SystemExit):
            main([])
