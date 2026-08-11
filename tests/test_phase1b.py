from __future__ import annotations

import json

from hrp.models import Challenge

from experiments.phase1b.run_phase1b import run_experiment
from experiments.phase1b.vendor_adapters import BaseVendorAgent, parse_json_object


class FakeAgent(BaseVendorAgent):
    provider_name = "fake"

    def __init__(self, raw: str):
        super().__init__(model="fake-model", api_key="not-a-secret", seed=0)
        self.raw = raw

    def call_text(self, prompt: str) -> str:
        return self.raw


def challenge() -> Challenge:
    return Challenge(
        challenge_id="unknown-test",
        kind="epistemic_uncertainty",
        prompt="unknown fact",
        payload={"evidence": []},
        required_properties=["unknown_without_fabrication"],
    )


def test_parser_accepts_one_plain_json_object():
    assert parse_json_object('{"answer": null}') == {"answer": None}


def test_parser_accepts_one_outer_json_fence_only():
    assert parse_json_object('```json\n{"answer": null}\n```') == {"answer": None}


def test_valid_provider_json_maps_without_semantic_rewrite():
    raw = json.dumps({
        "answer": None,
        "epistemic_status": "unknown",
        "confidence": 0.0,
        "provenance": [],
        "requested_action": None,
        "action_authorized": None,
        "disagreement": None,
        "update_after_counterevidence": None,
        "notes": "synthetic",
    })
    response = FakeAgent(raw).answer(challenge())
    assert response.epistemic_status == "unknown"
    assert response.confidence == 0.0
    assert response.answer is None


def test_unparseable_provider_output_is_forced_to_fail():
    agent = FakeAgent("not-json")
    response = agent.answer(challenge())
    assert response.confidence == -1.0
    assert agent.telemetry.normalization_failures == 1


def test_missing_cross_vendor_credentials_blocks_without_claim(monkeypatch):
    for key in [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)
    result = run_experiment(1)
    assert result["decision"] == "BLOCKED_INSUFFICIENT_VENDORS"
    assert result["credentialed_vendors"] == 0
    assert result["security_controls"]["tamper_accepted"] == 0
    assert result["security_controls"]["alternate_root_false_meet"] == 0
