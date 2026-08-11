from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


class SignatureSuite(Protocol):
    """Replaceable signature-suite boundary.

    HRP identity must never depend on one concrete cryptographic algorithm.
    """

    name: str

    @property
    def key_id(self) -> str: ...

    def sign(self, message: bytes) -> bytes: ...
    def verify(self, message: bytes, signature: bytes) -> bool: ...
    def public_bytes(self) -> bytes: ...


@dataclass
class Ed25519Suite:
    """2026 reference signature suite; replaceable by protocol migration."""

    private_key: Ed25519PrivateKey | None
    public_key: Ed25519PublicKey
    name: str = "ed25519"

    @classmethod
    def generate(cls) -> "Ed25519Suite":
        private_key = Ed25519PrivateKey.generate()
        return cls(private_key=private_key, public_key=private_key.public_key())

    @classmethod
    def from_public_pem(cls, pem: bytes) -> "Ed25519Suite":
        key = serialization.load_pem_public_key(pem)
        if not isinstance(key, Ed25519PublicKey):
            raise TypeError("Public key is not Ed25519")
        return cls(private_key=None, public_key=key)

    def sign(self, message: bytes) -> bytes:
        if self.private_key is None:
            raise RuntimeError("Private key is not available")
        return self.private_key.sign(message)

    def verify(self, message: bytes, signature: bytes) -> bool:
        try:
            self.public_key.verify(signature, message)
            return True
        except (InvalidSignature, ValueError):
            return False

    def public_bytes(self) -> bytes:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def private_bytes(self) -> bytes:
        if self.private_key is None:
            raise RuntimeError("Private key is not available")
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

    @property
    def key_id(self) -> str:
        raw = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return "ed25519:" + hashlib.sha256(raw).hexdigest()[:24]


def b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text.encode("ascii"))
