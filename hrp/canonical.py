from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Deterministic UTF-8 JSON encoding used for roots and proofs."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest_hex(value: Any, algorithm: str = "sha3_256") -> str:
    data = canonical_json_bytes(value)
    try:
        h = hashlib.new(algorithm)
    except ValueError as exc:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}") from exc
    h.update(data)
    return h.hexdigest()


def content_address(value: Any, algorithm: str = "sha3_256") -> str:
    return f"{algorithm}:{digest_hex(value, algorithm)}"
