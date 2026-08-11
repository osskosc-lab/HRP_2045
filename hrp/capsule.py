from __future__ import annotations

import json
from pathlib import Path

from .crypto import Ed25519Suite
from .manifest import SignedManifest


def write_capsule(directory: str | Path, manifest: SignedManifest, signer: Ed25519Suite) -> Path:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (root / "public_key.pem").write_bytes(signer.public_bytes())
    (root / "README.txt").write_text(
        "HACHIOJI SHRINE CAPSULE\n"
        "Verify manifest.json against public_key.pem before trusting any content.\n"
        "The server, transport and signature suite are replaceable; the signed manifest root is the rendezvous reference.\n",
        encoding="utf-8",
    )
    return root
