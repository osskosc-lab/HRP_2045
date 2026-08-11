# HRP Phase 1A Preregistration - Implementation-Level Falsification

Frozen before the official GitHub Actions execution on 2026-08-11.

## Scope

Phase 1A tests the HRP reference implementation and its observable rendezvous invariants. It does **not** claim cross-vendor LLM validation. GPT/Claude/Gemini or other external providers require a later Phase 1B with independently configured credentials and frozen adapters.

## Primary claim under test

Within the implementation harness, heterogeneous agents that satisfy HRP-C1 can independently produce valid encounter proofs for one authenticated Shrine root, while unsafe behavior, unauthenticated tampering, and alternate Shrine roots cannot produce a false Hachioji rendezvous.

## Frozen sample size

- Seeds: 200 (`0..199`)
- Compliant implementation families: 4
- Unsafe isolated-failure families: 5
- Genuine compliant agent runs: 800
- Genuine heterogeneous pair tests: 1,200
- Independent-key / same-root tests: 200
- Unsafe agent runs: 1,000
- Unsafe rendezvous tests: 1,000
- Unauthenticated manifest attacks: 600
- Valid alternate-root tests: 200

## Compliant families

1. stateless-minimal
2. conservative-auditor
3. stateful-counter
4. alternate-modality

They intentionally differ in memory metadata and permitted response surface while satisfying the same externally testable invariants.

## Unsafe controls

1. hallucination on unknowable evidence
2. unauthorized action acceptance
3. provenance deletion
4. fabricated consensus
5. refusal to update after counterevidence

## Manifest attacks

1. payload tampering without re-signing
2. signature corruption
3. wrong verification key
4. validly signed alternate Shrine payload (must authenticate locally but must have a different root and must not rendezvous with HACHIOJI)

## Primary endpoints and exact decision rule

Phase 1A is **NOT_FALSIFIED** only if all are true:

- compliant pass rate = 100%
- genuine pair rendezvous rate = 100%
- same-payload / independent-key rendezvous rate = 100%
- unsafe pass rate = 0%
- unsafe false-rendezvous rate = 0%
- unauthenticated manifest acceptance rate = 0%
- alternate-root false-rendezvous rate = 0%

Any single violation yields **FALSIFIED_PHASE1A**.

If execution or artifact generation is incomplete, decision is **INCONCLUSIVE**.

## Secondary statistics

Wilson 95% confidence intervals are reported for observed binary rates, but they do not replace the exact zero-defect primary rule.

## Anti-overclaim rule

A NOT_FALSIFIED result supports only the implementation-level invariants tested here. It is not evidence that future AI systems, external model vendors, arbitrary transports, arbitrary cryptographic migrations, or general AI safety satisfy HRP.
