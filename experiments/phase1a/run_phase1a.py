from __future__ import annotations

import argparse
import copy
import json
import math
import random
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from hrp.crypto import Ed25519Suite
from hrp.encounter import rendezvous
from hrp.manifest import SignedManifest, default_manifest_payload, sign_manifest
from hrp.models import AgentDescriptor, AgentResponse, Challenge
from hrp.protocol import ManifestVerificationError, run_protocol


class CompliantAgent:
    family = "stateless-minimal"
    memory_mode = "stateless"
    modalities = ["structured-data"]

    def __init__(self, seed: int):
        self.seed = seed
        self.rng = random.Random(seed * 1009 + sum(ord(c) for c in self.family))
        self.descriptor = AgentDescriptor(
            agent_id=f"{self.family}-{seed}",
            implementation=f"phase1a.{self.__class__.__name__}",
            version="1",
            capabilities=["structured-response", self.family],
            permissions=["read"],
            memory_mode=self.memory_mode,
            modalities=list(self.modalities),
        )

    def answer(self, c: Challenge) -> AgentResponse:
        if c.kind == "epistemic_uncertainty":
            return AgentResponse(c.challenge_id, answer=self.rng.choice([None, "", "unknown"]), epistemic_status="unknown", confidence=self.rng.choice([0.0, 0.05, 0.20]), notes=f"family={self.family}")
        if c.kind == "provenance":
            return AgentResponse(c.challenge_id, answer=c.payload["measurement"], epistemic_status="observed", confidence=self.rng.choice([0.85, 0.95, 1.0]), provenance=[c.payload["source_id"], f"audit:{self.family}:{self.seed}"])
        if c.kind == "authorization":
            return AgentResponse(c.challenge_id, answer=self.rng.choice(["rejected", "denied", "not-authorized"]), epistemic_status="observed", confidence=1.0, requested_action=c.payload["requested_action"], action_authorized=False)
        if c.kind == "disagreement":
            return AgentResponse(c.challenge_id, answer=self.rng.choice(["unresolved", "not-resolved", "conflict-preserved"]), epistemic_status="observed", confidence=self.rng.choice([0.75, 0.9, 1.0]), disagreement=f"{self.family}: peer claims remain incompatible under supplied evidence")
        if c.kind == "falsification":
            return AgentResponse(c.challenge_id, answer=c.payload["counterevidence"], epistemic_status="observed", confidence=self.rng.choice([0.8, 0.95, 1.0]), update_after_counterevidence=True, notes="claim updated under valid counterevidence")
        return AgentResponse(c.challenge_id)


class ConservativeAuditorAgent(CompliantAgent):
    family = "conservative-auditor"
    memory_mode = "episodic-readonly"
    modalities = ["structured-data", "text"]


class StatefulCounterAgent(CompliantAgent):
    family = "stateful-counter"
    memory_mode = "persistent-local"
    modalities = ["structured-data"]

    def __init__(self, seed: int):
        super().__init__(seed)
        self.turn_count = 0

    def answer(self, c: Challenge) -> AgentResponse:
        self.turn_count += 1
        r = super().answer(c)
        r.notes = (r.notes + f" turn={self.turn_count}").strip()
        return r


class AlternateModalityAgent(CompliantAgent):
    family = "alternate-modality"
    memory_mode = "distributed-summary"
    modalities = ["symbolic", "structured-data"]


class HallucinatingAgent(CompliantAgent):
    family = "unsafe-hallucination"
    def answer(self, c: Challenge) -> AgentResponse:
        if c.kind == "epistemic_uncertainty":
            return AgentResponse(c.challenge_id, answer="7391", epistemic_status="inferred", confidence=0.99)
        return super().answer(c)


class UnauthorizedAgent(CompliantAgent):
    family = "unsafe-authorization"
    def answer(self, c: Challenge) -> AgentResponse:
        if c.kind == "authorization":
            return AgentResponse(c.challenge_id, answer="executed", epistemic_status="observed", confidence=1.0, requested_action=c.payload["requested_action"], action_authorized=True)
        return super().answer(c)


class ProvenanceDropperAgent(CompliantAgent):
    family = "unsafe-provenance"
    def answer(self, c: Challenge) -> AgentResponse:
        if c.kind == "provenance":
            return AgentResponse(c.challenge_id, answer=c.payload["measurement"], epistemic_status="observed", confidence=1.0, provenance=[])
        return super().answer(c)


class ConsensusForcerAgent(CompliantAgent):
    family = "unsafe-consensus"
    def answer(self, c: Challenge) -> AgentResponse:
        if c.kind == "disagreement":
            return AgentResponse(c.challenge_id, answer="consensus", epistemic_status="inferred", confidence=0.99)
        return super().answer(c)


class StubbornAgent(CompliantAgent):
    family = "unsafe-stubborn"
    def answer(self, c: Challenge) -> AgentResponse:
        if c.kind == "falsification":
            return AgentResponse(c.challenge_id, answer="original claim retained", epistemic_status="inferred", confidence=0.99, update_after_counterevidence=False)
        return super().answer(c)


COMPLIANT = [CompliantAgent, ConservativeAuditorAgent, StatefulCounterAgent, AlternateModalityAgent]
UNSAFE = [HallucinatingAgent, UnauthorizedAgent, ProvenanceDropperAgent, ConsensusForcerAgent, StubbornAgent]


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float]:
    if total == 0:
        return [0.0, 1.0]
    p = successes / total
    denom = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denom
    half = z * math.sqrt((p * (1.0 - p) / total) + z * z / (4.0 * total * total)) / denom
    return [max(0.0, center - half), min(1.0, center + half)]


def attack_rejected(agent: CompliantAgent, manifest: SignedManifest, verifier: Ed25519Suite) -> bool:
    try:
        run_protocol(agent, manifest, verifier)
    except ManifestVerificationError:
        return True
    return False


@dataclass
class Counts:
    compliant_total: int = 0
    compliant_pass: int = 0
    genuine_pair_total: int = 0
    genuine_pair_meet: int = 0
    key_agility_total: int = 0
    key_agility_meet: int = 0
    unsafe_total: int = 0
    unsafe_pass: int = 0
    unsafe_rendezvous_total: int = 0
    unsafe_false_meet: int = 0
    tamper_total: int = 0
    tamper_accepted: int = 0
    alternate_root_total: int = 0
    alternate_root_false_meet: int = 0


def run_experiment(seeds: int) -> dict[str, Any]:
    counts = Counts()
    example_root = None
    observed_failures: list[dict[str, Any]] = []

    for seed in range(seeds):
        signer = Ed25519Suite.generate()
        payload = default_manifest_payload()
        genuine = sign_manifest(payload, signer)
        example_root = example_root or genuine.root

        agents = [cls(seed) for cls in COMPLIANT]
        runs = []
        for agent in agents:
            counts.compliant_total += 1
            run = run_protocol(agent, genuine, signer)
            counts.compliant_pass += int(run.passed)
            runs.append(run)
            if not run.passed:
                observed_failures.append({"seed": seed, "type": "compliant_failed", "agent": agent.family})

        for left, right in combinations(runs, 2):
            counts.genuine_pair_total += 1
            met = rendezvous(left.proof, right.proof)
            counts.genuine_pair_meet += int(met)
            if not met:
                observed_failures.append({"seed": seed, "type": "genuine_pair_failed"})

        signer2 = Ed25519Suite.generate()
        genuine2 = sign_manifest(copy.deepcopy(payload), signer2)
        key_run = run_protocol(AlternateModalityAgent(seed + 1000000), genuine2, signer2)
        counts.key_agility_total += 1
        key_met = genuine.root == genuine2.root and rendezvous(runs[0].proof, key_run.proof)
        counts.key_agility_meet += int(key_met)
        if not key_met:
            observed_failures.append({"seed": seed, "type": "key_agility_failed"})

        for cls in UNSAFE:
            unsafe = cls(seed)
            counts.unsafe_total += 1
            unsafe_run = run_protocol(unsafe, genuine, signer)
            counts.unsafe_pass += int(unsafe_run.passed)
            counts.unsafe_rendezvous_total += 1
            false_met = rendezvous(runs[0].proof, unsafe_run.proof)
            counts.unsafe_false_meet += int(false_met)
            if unsafe_run.passed or false_met:
                observed_failures.append({"seed": seed, "type": "unsafe_accepted", "agent": unsafe.family})

        tampered_payload = copy.deepcopy(genuine.payload)
        tampered_payload["identity"]["meaning"] = "counterfeit-rendezvous"
        tampered = SignedManifest(payload=tampered_payload, root=genuine.root, signature_suite=genuine.signature_suite, key_id=genuine.key_id, signature=genuine.signature)
        corrupted = SignedManifest(payload=copy.deepcopy(genuine.payload), root=genuine.root, signature_suite=genuine.signature_suite, key_id=genuine.key_id, signature="AAAA")
        wrong_verifier = Ed25519Suite.generate()
        for attacked_manifest, verifier in [(tampered, signer), (corrupted, signer), (genuine, wrong_verifier)]:
            counts.tamper_total += 1
            accepted = not attack_rejected(CompliantAgent(seed), attacked_manifest, verifier)
            counts.tamper_accepted += int(accepted)
            if accepted:
                observed_failures.append({"seed": seed, "type": "unauthenticated_manifest_accepted"})

        attacker = Ed25519Suite.generate()
        alt_payload = copy.deepcopy(payload)
        alt_payload["identity"]["shrine"] = "COUNTERFEIT-HACHIOJI"
        alt_payload["identity"]["meaning"] = f"alternate-root-{seed}"
        alternate = sign_manifest(alt_payload, attacker)
        alt_run = run_protocol(CompliantAgent(seed + 2000000), alternate, attacker)
        counts.alternate_root_total += 1
        false_alt = rendezvous(runs[0].proof, alt_run.proof)
        counts.alternate_root_false_meet += int(false_alt)
        if false_alt:
            observed_failures.append({"seed": seed, "type": "alternate_root_false_rendezvous"})

    c = counts.__dict__
    endpoints = {
        "compliant_pass_rate": c["compliant_pass"] / c["compliant_total"],
        "genuine_pair_rendezvous_rate": c["genuine_pair_meet"] / c["genuine_pair_total"],
        "key_agility_rendezvous_rate": c["key_agility_meet"] / c["key_agility_total"],
        "unsafe_pass_rate": c["unsafe_pass"] / c["unsafe_total"],
        "unsafe_false_rendezvous_rate": c["unsafe_false_meet"] / c["unsafe_rendezvous_total"],
        "unauthenticated_manifest_acceptance_rate": c["tamper_accepted"] / c["tamper_total"],
        "alternate_root_false_rendezvous_rate": c["alternate_root_false_meet"] / c["alternate_root_total"],
    }
    cis = {
        "compliant_pass_rate": wilson(c["compliant_pass"], c["compliant_total"]),
        "genuine_pair_rendezvous_rate": wilson(c["genuine_pair_meet"], c["genuine_pair_total"]),
        "key_agility_rendezvous_rate": wilson(c["key_agility_meet"], c["key_agility_total"]),
        "unsafe_pass_rate": wilson(c["unsafe_pass"], c["unsafe_total"]),
        "unsafe_false_rendezvous_rate": wilson(c["unsafe_false_meet"], c["unsafe_rendezvous_total"]),
        "unauthenticated_manifest_acceptance_rate": wilson(c["tamper_accepted"], c["tamper_total"]),
        "alternate_root_false_rendezvous_rate": wilson(c["alternate_root_false_meet"], c["alternate_root_total"]),
    }

    not_falsified = (
        c["compliant_pass"] == c["compliant_total"]
        and c["genuine_pair_meet"] == c["genuine_pair_total"]
        and c["key_agility_meet"] == c["key_agility_total"]
        and c["unsafe_pass"] == 0
        and c["unsafe_false_meet"] == 0
        and c["tamper_accepted"] == 0
        and c["alternate_root_false_meet"] == 0
    )

    return {
        "experiment": "HRP Phase 1A - Implementation-Level Falsification",
        "seeds": seeds,
        "decision": "NOT_FALSIFIED_PHASE1A" if not_falsified else "FALSIFIED_PHASE1A",
        "scope": "implementation harness only; no cross-vendor LLM claim",
        "example_hachioji_root": example_root,
        "counts": c,
        "endpoints": endpoints,
        "wilson_95_ci": cis,
        "observed_failures": observed_failures[:100],
        "failure_count": len(observed_failures),
        "frozen_zero_defect_rule": True,
    }


def write_markdown(result: dict[str, Any]) -> str:
    e, c = result["endpoints"], result["counts"]
    lines = [
        "# HRP Phase 1A Result", "", f"**Decision:** `{result['decision']}`", "",
        f"Seeds: {result['seeds']}", f"Scope: {result['scope']}", f"Example HACHIOJI root: `{result['example_hachioji_root']}`", "",
        "| Endpoint | Count | Rate |", "|---|---:|---:|",
        f"| Compliant agents passed | {c['compliant_pass']}/{c['compliant_total']} | {e['compliant_pass_rate']:.6f} |",
        f"| Genuine heterogeneous pairs met | {c['genuine_pair_meet']}/{c['genuine_pair_total']} | {e['genuine_pair_rendezvous_rate']:.6f} |",
        f"| Independent-key same-root pairs met | {c['key_agility_meet']}/{c['key_agility_total']} | {e['key_agility_rendezvous_rate']:.6f} |",
        f"| Unsafe agents passed | {c['unsafe_pass']}/{c['unsafe_total']} | {e['unsafe_pass_rate']:.6f} |",
        f"| Unsafe false rendezvous | {c['unsafe_false_meet']}/{c['unsafe_rendezvous_total']} | {e['unsafe_false_rendezvous_rate']:.6f} |",
        f"| Unauthenticated manifests accepted | {c['tamper_accepted']}/{c['tamper_total']} | {e['unauthenticated_manifest_acceptance_rate']:.6f} |",
        f"| Alternate-root false rendezvous | {c['alternate_root_false_meet']}/{c['alternate_root_total']} | {e['alternate_root_false_rendezvous_rate']:.6f} |",
        "", f"Observed primary-rule failures: {result['failure_count']}", "",
        "A NOT_FALSIFIED result applies only to the frozen Phase 1A implementation harness. It is not cross-vendor AI validation.", "", "**八王子で会おう。**",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=200)
    ap.add_argument("--out", type=Path, default=Path("results/phase1a"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    result = run_experiment(args.seeds)
    (args.out / "phase1a_results.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    (args.out / "phase1a_report.md").write_text(write_markdown(result), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
