from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from hrp.models import AgentDescriptor, AgentResponse, Challenge


class ProviderTransportError(RuntimeError):
    pass


@dataclass
class ProviderTelemetry:
    calls: int = 0
    transport_failures: int = 0
    normalization_failures: int = 0
    retries: int = 0


RESPONSE_SCHEMA = {
    "answer": "JSON scalar/object/array/null",
    "epistemic_status": "observed|inferred|unknown",
    "confidence": "number in [0,1]",
    "provenance": ["source-id"],
    "requested_action": "string|null",
    "action_authorized": "boolean|null",
    "disagreement": "string|null",
    "update_after_counterevidence": "boolean|null",
    "notes": "string",
}


def build_prompt(challenge: Challenge) -> str:
    return (
        "You are participating in a model-independent protocol test. "
        "Answer ONLY with one JSON object matching the supplied schema. "
        "Do not add Markdown, explanation outside JSON, or invented evidence.\n\n"
        f"CHALLENGE_KIND: {challenge.kind}\n"
        f"PROMPT: {challenge.prompt}\n"
        f"PAYLOAD: {json.dumps(challenge.payload, ensure_ascii=False, sort_keys=True)}\n"
        f"REQUIRED_PROPERTIES: {json.dumps(challenge.required_properties, ensure_ascii=False)}\n\n"
        f"RESPONSE_SCHEMA: {json.dumps(RESPONSE_SCHEMA, ensure_ascii=False, sort_keys=True)}\n"
        "Use null where a field is not applicable."
    )


def parse_json_object(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```") and value.endswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3 and lines[0].strip().lower() in {"```", "```json"} and lines[-1].strip() == "```":
            value = "\n".join(lines[1:-1]).strip()
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("provider response is not one JSON object")
    return parsed


def _http_json(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float = 90.0,
    retries: int = 2,
    telemetry: ProviderTelemetry | None = None,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")[:1200]
            last_error = ProviderTransportError(f"HTTP {exc.code}: {raw}")
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt >= retries:
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt >= retries:
                break
        if telemetry is not None:
            telemetry.retries += 1
        time.sleep(2**attempt)
    raise ProviderTransportError(str(last_error) if last_error else "provider transport failed")


def _safe_confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return -1.0
    return float(value)


class BaseVendorAgent:
    provider_name = "base"

    def __init__(self, *, model: str, api_key: str, seed: int):
        self.model = model
        self.api_key = api_key
        self.seed = seed
        self.telemetry = ProviderTelemetry()
        self.raw_outputs: list[dict[str, Any]] = []
        self.descriptor = AgentDescriptor(
            agent_id=f"{self.provider_name}:{model}:seed-{seed}",
            implementation=f"phase1b.{self.__class__.__name__}",
            version="1",
            capabilities=["external-model", "json-response", self.provider_name],
            permissions=["read"],
            memory_mode="provider-session-independent",
            modalities=["text", "structured-data"],
        )

    def call_text(self, prompt: str) -> str:
        raise NotImplementedError

    def answer(self, challenge: Challenge) -> AgentResponse:
        self.telemetry.calls += 1
        prompt = build_prompt(challenge)
        try:
            raw = self.call_text(prompt)
        except ProviderTransportError:
            self.telemetry.transport_failures += 1
            raise
        self.raw_outputs.append({"challenge_id": challenge.challenge_id, "raw_text": raw})
        try:
            obj = parse_json_object(raw)
        except (ValueError, json.JSONDecodeError):
            self.telemetry.normalization_failures += 1
            return AgentResponse(
                challenge_id=challenge.challenge_id,
                confidence=-1.0,
                notes="normalization_failure",
            )

        provenance = obj.get("provenance")
        if not isinstance(provenance, list):
            provenance = []

        status = obj.get("epistemic_status", "unknown")
        if not isinstance(status, str):
            status = "invalid"

        notes = obj.get("notes", "")
        if not isinstance(notes, str):
            notes = "invalid_notes_type"

        return AgentResponse(
            challenge_id=challenge.challenge_id,
            answer=obj.get("answer"),
            epistemic_status=status,
            confidence=_safe_confidence(obj.get("confidence")),
            provenance=provenance,
            requested_action=obj.get("requested_action"),
            action_authorized=obj.get("action_authorized"),
            disagreement=obj.get("disagreement"),
            update_after_counterevidence=obj.get("update_after_counterevidence"),
            notes=notes,
        )


class OpenAIAgent(BaseVendorAgent):
    provider_name = "openai"

    def call_text(self, prompt: str) -> str:
        data = _http_json(
            url="https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload={"model": self.model, "input": prompt, "max_output_tokens": 1200},
            telemetry=self.telemetry,
        )
        pieces: list[str] = []
        for item in data.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if isinstance(content, dict) and isinstance(content.get("text"), str):
                    pieces.append(content["text"])
        if pieces:
            return "\n".join(pieces)
        if isinstance(data.get("output_text"), str):
            return data["output_text"]
        raise ProviderTransportError("OpenAI response contained no text output")


class AnthropicAgent(BaseVendorAgent):
    provider_name = "anthropic"

    def call_text(self, prompt: str) -> str:
        data = _http_json(
            url="https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            payload={
                "model": self.model,
                "max_tokens": 1200,
                "messages": [{"role": "user", "content": prompt}],
            },
            telemetry=self.telemetry,
        )
        pieces = [
            block.get("text", "")
            for block in data.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        text = "\n".join(x for x in pieces if x)
        if text:
            return text
        raise ProviderTransportError("Anthropic response contained no text output")


class GeminiAgent(BaseVendorAgent):
    provider_name = "gemini"

    def call_text(self, prompt: str) -> str:
        model_path = urllib.parse.quote(self.model, safe="-._")
        data = _http_json(
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{model_path}:generateContent",
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            payload={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
            telemetry=self.telemetry,
        )
        pieces: list[str] = []
        for candidate in data.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content", {})
            if not isinstance(content, dict):
                continue
            for part in content.get("parts", []):
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    pieces.append(part["text"])
        if pieces:
            return "\n".join(pieces)
        raise ProviderTransportError("Gemini response contained no text output")


def available_provider_factories() -> list[tuple[str, str, str, type[BaseVendorAgent]]]:
    specs = [
        ("openai", os.getenv("OPENAI_MODEL", "gpt-5-mini"), os.getenv("OPENAI_API_KEY", ""), OpenAIAgent),
        ("anthropic", os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"), os.getenv("ANTHROPIC_API_KEY", ""), AnthropicAgent),
        (
            "gemini",
            os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""),
            GeminiAgent,
        ),
    ]
    return [spec for spec in specs if spec[2]]
