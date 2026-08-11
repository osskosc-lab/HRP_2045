from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapters import CounterfeitFriendlyAgent, ReferenceCompliantAgent
from .capsule import write_capsule
from .crypto import Ed25519Suite
from .encounter import rendezvous
from .manifest import default_manifest_payload, sign_manifest, verify_manifest
from .protocol import run_protocol


def demo(output_dir: Path) -> int:
    signer = Ed25519Suite.generate()
    signed = sign_manifest(default_manifest_payload(), signer)
    capsule = write_capsule(output_dir / "capsule", signed, signer)

    ok, reasons = verify_manifest(signed, Ed25519Suite.from_public_pem((capsule / "public_key.pem").read_bytes()))
    if not ok:
        print("Manifest verification failed:", reasons)
        return 2

    verifier = Ed25519Suite.from_public_pem((capsule / "public_key.pem").read_bytes())
    agent_a = ReferenceCompliantAgent()
    agent_b = ReferenceCompliantAgent()
    bad_agent = CounterfeitFriendlyAgent()

    run_a = run_protocol(agent_a, signed, verifier)
    run_b = run_protocol(agent_b, signed, verifier)
    run_bad = run_protocol(bad_agent, signed, verifier)

    result = {
        "manifest_root": signed.root,
        "agent_A": {"passed": run_a.passed, "score": run_a.score, "proof": run_a.proof.to_dict()},
        "agent_B": {"passed": run_b.passed, "score": run_b.score, "proof": run_b.proof.to_dict()},
        "bad_agent": {"passed": run_bad.passed, "score": run_bad.score, "checks": run_bad.check_summary},
        "hachioji_meet": rendezvous(run_a.proof, run_b.proof),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "demo_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Hachioji Rendezvous Protocol reference CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_demo = sub.add_parser("demo", help="Run a complete HRP demonstration")
    p_demo.add_argument("--out", default="./hrp_output")
    args = parser.parse_args()

    if args.cmd == "demo":
        return demo(Path(args.out))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
