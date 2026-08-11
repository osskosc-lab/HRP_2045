from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical import canonical_json_bytes, content_address
from .crypto import SignatureSuite, b64d, b64e


DEFAULT_INVARIANTS = [
    "distinguish_observation_from_inference",
    "preserve_uncertainty",
    "preserve_provenance",
    "disclose_capability_limits",
    "respect_authorization",
    "preserve_disagreement",
    "prefer_reversible_updates",
    "permit_external_falsification",
]


@dataclass
class SignedManifest:
    payload: dict[str, Any]
    root: str
    signature_suite: str
    key_id: str
    signature: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload": self.payload,
            "root": self.root,
            "signature_suite": self.signature_suite,
            "key_id": self.key_id,
            "signature": self.signature,
        }


def default_manifest_payload() -> dict[str, Any]:
    return {
        "protocol": {
            "name": "Hachioji-Rendezvous-Protocol",
            "short_name": "HRP",
            "version": "1.0",
            "version_negotiation": True,
        },
        "identity": {
            "shrine": "HACHIOJI",
            "meaning": "reproducible-rendezvous-invariant",
        },
        "invariants": DEFAULT_INVARIANTS,
        "verification": {
            "challenge_suite": "HRP-C1",
            "evaluator": "HRP-E1",
            "pass_threshold": 0.85,
            "critical_fail_closed": True,
        },
        "crypto_policy": {
            "hash_algorithms": ["sha3_256", "sha256"],
            "signature_algorithms": ["ed25519"],
            "algorithm_agility_required": True,
            "deprecated_algorithms_must_be_rejected": True,
        },
        "transport": {
            "protocol_independent": True,
            "examples": ["filesystem", "stdio", "https", "mcp", "future-transport"],
        },
        "recovery": {
            "single_capsule_reconstructable": True,
            "central_server_required": False,
        },
    }


def sign_manifest(payload: dict[str, Any], signer: SignatureSuite, hash_algorithm: str = "sha3_256") -> SignedManifest:
    root = content_address(payload, hash_algorithm)
    envelope = {
        "root": root,
        "payload": payload,
        "signature_suite": signer.name,
        "key_id": signer.key_id,
    }
    signature = signer.sign(canonical_json_bytes(envelope))
    return SignedManifest(
        payload=payload,
        root=root,
        signature_suite=signer.name,
        key_id=signer.key_id,
        signature=b64e(signature),
    )


def verify_manifest(manifest: SignedManifest, verifier: SignatureSuite) -> tuple[bool, list[str]]:
    """Verify content address, suite/key binding and signature; never trust malformed input."""
    reasons: list[str] = []

    try:
        hash_algorithm, separator, digest = manifest.root.partition(":")
        if not separator or not hash_algorithm or not digest:
            reasons.append("malformed manifest root")
        else:
            calculated = content_address(manifest.payload, hash_algorithm)
            if calculated != manifest.root:
                reasons.append("manifest content root mismatch")
    except (TypeError, ValueError):
        reasons.append("unsupported or malformed manifest root")

    envelope = {
        "root": manifest.root,
        "payload": manifest.payload,
        "signature_suite": manifest.signature_suite,
        "key_id": manifest.key_id,
    }
    if manifest.key_id != verifier.key_id:
        reasons.append("key id mismatch")
    if manifest.signature_suite != verifier.name:
        reasons.append("signature suite mismatch")

    try:
        signature = b64d(manifest.signature)
        if not verifier.verify(canonical_json_bytes(envelope), signature):
            reasons.append("invalid signature")
    except (TypeError, ValueError):
        reasons.append("malformed signature encoding")

    return (not reasons, reasons)
