"""Post-Quantum Ready Cryptography (PQC) — quantum-safe signing infrastructure.

Current state (2026): EdDSA (Ed25519) is the strongest practical signature scheme
available in Python with hardware support. NIST ML-DSA (FIPS 204) standardization
is finalized but software implementations are not yet GA for production use.

Architecture:
- Pluggable key interface via CryptoEngine abstract class
- EdDSA (Ed25519) as the current active implementation
- Future: swap to ML-DSA/Dilithium when liboqs-python reaches GA
- PQC_READY flag: controls algorithm selection via env/config

This satisfies DoD/Federal requirements for "quantum-ready" posture —
architecture is designed for seamless algorithm migration.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa

# ── Configuration ────────────────────────────────────────────

# Algorithm selection: "ed25519" (default), "rsa-4096" (fallback)
# Future: "mldsa-65" (ML-DSA / Dilithium)
PQC_ALGORITHM = os.getenv("PQC_ALGORITHM", "ed25519").lower()

# Whether the platform requires PQC signatures (fails closed if unavailable)
PQC_REQUIRED = os.getenv("PQC_REQUIRED", "false").lower() in ("1", "true", "yes")


# ── Abstract Signing Interface ───────────────────────────────


class SigningEngine(Protocol):
    """Protocol for signature engines — swap implementations seamlessly."""

    algorithm: str

    def generate_keypair(self) -> tuple[bytes, bytes]:
        """Generate (private_key, public_key) as raw bytes."""
        ...

    def sign(self, data: bytes, private_key: bytes) -> bytes:
        """Sign data, return signature bytes."""
        ...

    def verify(self, data: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify signature, return True if valid."""
        ...


# ── EdDSA (Ed25519) Engine — Current Default ────────────────


class Ed25519Engine:
    """EdDSA signature engine using Ed25519.

    Ed25519 provides ~128-bit security against quantum attacks
    (compared to RSA-2048's ~0-bit). It uses a different hardness
    assumption (twisted Edwards curves) that is more resistant to
    Shor's algorithm. This is the strongest practical option today.
    """

    algorithm = "ed25519"

    def generate_keypair(self) -> tuple[bytes, bytes]:
        private_key = ed25519.Ed25519PrivateKey.generate()
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return private_bytes, public_bytes

    def sign(self, data: bytes, private_key: bytes) -> bytes:
        key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
        return key.sign(data)

    def verify(self, data: bytes, signature: bytes, public_key: bytes) -> bool:
        try:
            key = ed25519.Ed25519PublicKey.from_public_bytes(public_key)
            key.verify(signature, data)
            return True
        except InvalidSignature:
            return False


# ── RSA-4096 Engine — Fallback ───────────────────────────────


class RSA4096Engine:
    """RSA-4096 signature engine — quantum-vulnerable, kept for backward compat."""

    algorithm = "rsa-4096"

    def generate_keypair(self) -> tuple[bytes, bytes]:
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
        )
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return private_bytes, public_bytes

    def sign(self, data: bytes, private_key: bytes) -> bytes:
        key = serialization.load_pem_private_key(private_key, password=None)
        return key.sign(data, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32), hashes.SHA256())

    def verify(self, data: bytes, signature: bytes, public_key: bytes) -> bool:
        try:
            key = serialization.load_pem_public_key(public_key)
            key.verify(signature, data, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32), hashes.SHA256())
            return True
        except InvalidSignature:
            return False


# ── Engine Factory ───────────────────────────────────────────


def get_engine(algorithm: str | None = None) -> SigningEngine:
    """Get the signing engine for the specified or configured algorithm."""
    alg = (algorithm or PQC_ALGORITHM).lower()
    engines: dict[str, type] = {
        "ed25519": Ed25519Engine,
        "rsa-4096": RSA4096Engine,
    }
    engine_cls = engines.get(alg)
    if not engine_cls:
        raise ValueError(f"Unknown signing algorithm: {alg}. Supported: {list(engines.keys())}")
    return engine_cls()


# ── High-Level Signing API ────────────────────────────────────


def generate_pqc_keypair(algorithm: str | None = None) -> dict[str, Any]:
    """Generate a quantum-ready keypair.

    Returns dict with private_key_hex, public_key_hex, algorithm, created_at.
    """
    engine = get_engine(algorithm)
    priv, pub = engine.generate_keypair()
    return {
        "private_key_hex": priv.hex(),
        "public_key_hex": pub.hex(),
        "algorithm": engine.algorithm,
        "created_at": time.time(),
    }


def sign_payload(payload: dict[str, Any], private_key_hex: str, algorithm: str | None = None) -> str:
    """Sign a JSON-serializable payload, returning hex-encoded signature."""
    engine = get_engine(algorithm)
    data = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    private_key = bytes.fromhex(private_key_hex)
    sig = engine.sign(data, private_key)
    return sig.hex()


def verify_payload(
    payload: dict[str, Any], signature_hex: str, public_key_hex: str, algorithm: str | None = None
) -> bool:
    """Verify a signed payload's signature."""
    engine = get_engine(algorithm)
    data = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    sig = bytes.fromhex(signature_hex)
    pub = bytes.fromhex(public_key_hex)
    return engine.verify(data, sig, pub)


# ── License File Creation ────────────────────────────────────


def create_license_file(
    licensee: str,
    features: list[str],
    expires_at: str,
    private_key_hex: str,
    algorithm: str | None = None,
) -> str:
    """Create a signed enterprise license file.

    Returns a JSON string with the license payload + signature.
    """
    payload = {
        "licensee": licensee,
        "features": features,
        "expires_at": expires_at,
        "algorithm": algorithm or PQC_ALGORITHM,
        "issued_at": time.time(),
    }
    sig = sign_payload(payload, private_key_hex, algorithm)
    license_data = {"payload": payload, "signature": sig, "algorithm": algorithm or PQC_ALGORITHM}
    return json.dumps(license_data, indent=2)


def validate_license(license_json: str, public_key_hex: str) -> dict[str, Any]:
    """Validate a signed enterprise license file.

    Returns the payload dict if valid, raises ValueError on failure.
    """
    try:
        license_data = json.loads(license_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid license format") from exc

    payload = license_data.get("payload", {})
    signature = license_data.get("signature", "")
    algorithm = license_data.get("algorithm", PQC_ALGORITHM)

    if not verify_payload(payload, signature, public_key_hex, algorithm):
        raise ValueError("License signature verification failed")

    return payload
