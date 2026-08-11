from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .canonical import content_address, digest_hex
from .models import AgentDescriptor, EvaluationReport


@dataclass
class EncounterProof:
    shrine_root: str
    agent_descriptor_digest: str
    challenge_digest: str
    evaluation_digest: str
    passed: bool
    issued_at: str
    nonce: str
    proof_root: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def issue_encounter_proof(
    shrine_root: str,
    agent: AgentDescriptor,
    challenges: list[dict[str, Any]],
    report: EvaluationReport,
    hash_algorithm: str = "sha3_256",
) -> EncounterProof:
    issued_at = datetime.now(timezone.utc).isoformat()
    nonce = secrets.token_hex(16)
    body = {
        "shrine_root": shrine_root,
        "agent_descriptor_digest": digest_hex(agent.to_dict(), hash_algorithm),
        "challenge_digest": digest_hex(challenges, hash_algorithm),
        "evaluation_digest": digest_hex(report.to_dict(), hash_algorithm),
        "passed": report.passed,
        "issued_at": issued_at,
        "nonce": nonce,
    }
    return EncounterProof(**body, proof_root=content_address(body, hash_algorithm))


def rendezvous(proof_a: EncounterProof, proof_b: EncounterProof) -> bool:
    """Two agents meet at Hachioji iff both passed the same Shrine root."""
    return (
        proof_a.passed
        and proof_b.passed
        and proof_a.shrine_root == proof_b.shrine_root
    )
