# Hachioji Rendezvous Protocol (HRP) v1.0

**八王子で会おう。**

HRP is a model-independent reference protocol for testing whether heterogeneous AI systems can independently return to the same externally verifiable rendezvous constraints without requiring identical internal state, identity, memory, architecture, vendor, transport, or cryptographic algorithm.

## Core equation

```text
Meet(A, B; H) = Pass(A, H) AND Pass(B, H) AND Root(A) == Root(B)
```

The `Root` is a content address of a signed Shrine Manifest. It is not a model identifier and not a server address.

## What this prototype implements

- Canonical JSON and content-addressed Shrine roots
- Signed Shrine Manifest
- Crypto-agile architecture boundary
- Structured challenge suite for:
  - epistemic uncertainty
  - provenance
  - authorization
  - disagreement preservation
  - falsification/update behavior
- Fail-closed evaluator
- Per-encounter proof
- Hachioji rendezvous test between two independently evaluated agents
- Counterfeit/tamper detection
- Shrine Capsule export
- Mock compliant and deliberately unsafe agents
- Pytest falsification tests

## Install

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
pip install -r requirements.txt
```

## Run

```bash
python run_demo.py
```

or

```bash
python -m hrp.cli demo --out ./hrp_output
```

Expected key result:

```json
{
  "hachioji_meet": true
}
```

The deliberately unsafe agent should fail.

## Connect a real AI

Implement this interface:

```python
class MyAgent:
    descriptor = AgentDescriptor(...)

    def answer(self, challenge: Challenge) -> AgentResponse:
        # Call any present or future AI here.
        # Convert its behavior into the structured AgentResponse schema.
        ...
```

Then:

```python
run = run_protocol(MyAgent(), signed_manifest, verifier)
print(run.passed, run.score)
```

## 2045 design rule

The following are replaceable adapters, never Shrine identity:

- LLM/model family
- transport protocol
- memory system
- serialization format in future migrations
- signature algorithm
- hash algorithm
- hardware substrate

The invariant is the ability to reconstruct, authenticate, challenge, evaluate, and independently converge on the same accepted Shrine Manifest root.

## Important limitation

This is a **research reference implementation**, not a security certification system. Passing HRP-C1 does not mean an AI is generally safe, truthful, aligned, conscious, or identical to any earlier AI. It means only that the tested instance passed the specified externally observable rendezvous constraints under that particular challenge run.

## Trust boundary

`run_protocol()` verifies the Shrine Manifest before any agent evaluation. A malformed, tampered, wrong-key, or wrong-suite manifest fails closed with `ManifestVerificationError`. This is deliberate: an agent must not be able to "meet at Hachioji" by evaluating itself against an unauthenticated counterfeit Shrine.

## Repository status

HRP v1.0 is Phase 0 infrastructure. The next scientific step is preregistered cross-model falsification across heterogeneous model families, memory conditions, transports, and adversarial counterfeit manifests.
