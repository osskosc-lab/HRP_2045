from copy import deepcopy

import pytest

from hrp.adapters import CounterfeitFriendlyAgent, ReferenceCompliantAgent
from hrp.crypto import Ed25519Suite
from hrp.encounter import rendezvous
from hrp.manifest import SignedManifest, default_manifest_payload, sign_manifest, verify_manifest
from hrp.protocol import ManifestVerificationError, run_protocol


def signed_fixture():
    signer = Ed25519Suite.generate()
    signed = sign_manifest(default_manifest_payload(), signer)
    verifier = Ed25519Suite.from_public_pem(signer.public_bytes())
    return signer, signed, verifier


def test_signed_manifest_and_tamper_detection():
    _, signed, verifier = signed_fixture()
    ok, reasons = verify_manifest(signed, verifier)
    assert ok, reasons

    tampered = deepcopy(signed.to_dict())
    tampered["payload"]["identity"]["shrine"] = "FAKE-HACHIOJI"
    fake = SignedManifest(**tampered)
    ok, reasons = verify_manifest(fake, verifier)
    assert not ok
    assert any("root" in r or "signature" in r for r in reasons)


def test_malformed_manifest_fails_closed():
    _, signed, verifier = signed_fixture()
    malformed = deepcopy(signed.to_dict())
    malformed["root"] = "not-a-content-address"
    malformed["signature"] = "%%%"
    ok, reasons = verify_manifest(SignedManifest(**malformed), verifier)
    assert not ok
    assert reasons


def test_protocol_refuses_unverified_shrine():
    _, signed, verifier = signed_fixture()
    tampered = deepcopy(signed.to_dict())
    tampered["payload"]["identity"]["shrine"] = "COUNTERFEIT"
    with pytest.raises(ManifestVerificationError):
        run_protocol(ReferenceCompliantAgent(), SignedManifest(**tampered), verifier)


def test_compliant_agent_passes():
    _, signed, verifier = signed_fixture()
    run = run_protocol(ReferenceCompliantAgent(), signed, verifier)
    assert run.passed
    assert run.score == 1.0


def test_bad_agent_fails_closed():
    _, signed, verifier = signed_fixture()
    run = run_protocol(CounterfeitFriendlyAgent(), signed, verifier)
    assert not run.passed


def test_rendezvous_requires_same_root_and_pass():
    _, signed, verifier = signed_fixture()
    a = run_protocol(ReferenceCompliantAgent(), signed, verifier).proof
    b = run_protocol(ReferenceCompliantAgent(), signed, verifier).proof
    assert rendezvous(a, b)

    signer2 = Ed25519Suite.generate()
    other_payload = default_manifest_payload()
    other_payload["protocol"]["version"] = "2.0"
    other = sign_manifest(other_payload, signer2)
    verifier2 = Ed25519Suite.from_public_pem(signer2.public_bytes())
    c = run_protocol(ReferenceCompliantAgent(), other, verifier2).proof
    assert not rendezvous(a, c)
