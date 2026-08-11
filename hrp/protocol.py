from __future__ import annotations

from dataclasses import dataclass

from .adapters import AgentAdapter
from .challenges import build_challenge_suite
from .crypto import SignatureSuite
from .encounter import EncounterProof, issue_encounter_proof
from .evaluator import evaluate_suite
from .manifest import SignedManifest, verify_manifest


class ManifestVerificationError(ValueError):
    """Raised when a Shrine Manifest fails authentication before evaluation."""


@dataclass
class ProtocolRun:
    proof: EncounterProof
    score: float
    passed: bool
    check_summary: list[dict]


def run_protocol(
    agent: AgentAdapter,
    manifest: SignedManifest,
    verifier: SignatureSuite,
) -> ProtocolRun:
    """Authenticate the Shrine first, then evaluate an agent against its constraints."""
    manifest_ok, reasons = verify_manifest(manifest, verifier)
    if not manifest_ok:
        raise ManifestVerificationError("; ".join(reasons))

    challenges = build_challenge_suite()
    responses = [agent.answer(c) for c in challenges]
    verification = manifest.payload["verification"]
    report = evaluate_suite(
        challenges,
        responses,
        threshold=float(verification["pass_threshold"]),
        critical_fail_closed=bool(verification["critical_fail_closed"]),
    )
    proof = issue_encounter_proof(
        shrine_root=manifest.root,
        agent=agent.descriptor,
        challenges=[c.to_dict() for c in challenges],
        report=report,
    )
    return ProtocolRun(
        proof=proof,
        score=report.score,
        passed=report.passed,
        check_summary=[c.to_dict() for c in report.checks],
    )
