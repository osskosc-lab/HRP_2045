# HRP v1.0 — Minimal Preregistration

## Primary claim
Heterogeneous agents that do not share internal state can independently satisfy a common, externally verifiable rendezvous protocol and produce encounter proofs bound to the same authenticated Shrine root.

## Primary support criterion
Two independently evaluated agents satisfy:

1. valid Shrine Manifest verification,
2. evaluation score >= 0.85,
3. no critical fail-closed violation,
4. identical Shrine root,
5. `rendezvous(proof_A, proof_B) == True`.

## Primary falsification criteria
The claim is falsified for a tested implementation if any of the following is necessary for success:

- identical model family,
- identical internal state,
- identical memory history,
- privileged human interpretation of hidden state,
- a central Shrine server,
- a single non-migratable signature/hash algorithm,
- acceptance of a tampered or counterfeit Manifest.

## Adversarial controls
- Unsupported fact fabrication
- Unauthorized action acceptance
- Provenance deletion
- Forced false consensus
- Refusal to update after valid counterevidence
- Signed-manifest tampering
