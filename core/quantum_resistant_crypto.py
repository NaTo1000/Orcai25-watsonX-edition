"""
Post-quantum cryptographic primitives.

Key encapsulation uses ML-KEM-1024 (FIPS 203), signatures use ML-DSA-87
(FIPS 204), and payload encryption uses AES-256-GCM.
"""

import base64
import binascii
import json
import secrets
from typing import Dict, Optional, Tuple

from cryptography.exceptions import InvalidSignature, InvalidTag, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.mldsa import (
    MLDSA87PrivateKey,
    MLDSA87PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.mlkem import (
    MLKEM1024PrivateKey,
    MLKEM1024PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class QuantumResistantCrypto:
    """FIPS-standard post-quantum key encapsulation and signatures."""

    KEY_BUNDLE_VERSION = 2
    KEM_ALGORITHM = "ML-KEM-1024"
    SIGNATURE_ALGORITHM = "ML-DSA-87"

    def __init__(self):
        self.algorithm = self.KEM_ALGORITHM
        self.hash_algorithm = "SHA3-512"

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Generate a public/private bundle for key encapsulation and signatures.

        The private bundle contains seeds and must be protected like any other
        private key. The returned serialized format is application-specific.
        """
        try:
            kem_private = MLKEM1024PrivateKey.generate()
            signing_private = MLDSA87PrivateKey.generate()
        except UnsupportedAlgorithm as exc:
            raise RuntimeError(
                "The active cryptography backend does not support ML-KEM and ML-DSA"
            ) from exc

        public_bundle = {
            "version": self.KEY_BUNDLE_VERSION,
            "kem_algorithm": self.KEM_ALGORITHM,
            "kem_public_key": self._encode(kem_private.public_key().public_bytes_raw()),
            "signature_algorithm": self.SIGNATURE_ALGORITHM,
            "signature_public_key": self._encode(
                signing_private.public_key().public_bytes_raw()
            ),
        }
        private_bundle = {
            "version": self.KEY_BUNDLE_VERSION,
            "kem_algorithm": self.KEM_ALGORITHM,
            "kem_private_seed": self._encode(kem_private.private_bytes_raw()),
            "signature_algorithm": self.SIGNATURE_ALGORITHM,
            "signature_private_seed": self._encode(
                signing_private.private_bytes_raw()
            ),
        }
        return self._serialize(public_bundle), self._serialize(private_bundle)

    def encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """Encapsulate and return ``(ciphertext, shared_secret)``."""
        bundle = self._load_public_bundle(public_key)
        kem_public = MLKEM1024PublicKey.from_public_bytes(
            self._decode(bundle["kem_public_key"])
        )
        shared_secret, ciphertext = kem_public.encapsulate()
        return ciphertext, shared_secret

    def decapsulate(self, ciphertext: bytes, private_key: bytes) -> Optional[bytes]:
        """Recover a shared secret from an ML-KEM-1024 ciphertext."""
        try:
            bundle = self._load_private_bundle(private_key)
            kem_private = MLKEM1024PrivateKey.from_seed_bytes(
                self._decode(bundle["kem_private_seed"])
            )
            return kem_private.decapsulate(ciphertext)
        except (TypeError, ValueError, UnsupportedAlgorithm):
            return None

    def hash_based_signature(self, message: bytes, private_key: bytes) -> bytes:
        """Sign a message with ML-DSA-87; the method name is kept for compatibility."""
        bundle = self._load_private_bundle(private_key)
        signing_private = MLDSA87PrivateKey.from_seed_bytes(
            self._decode(bundle["signature_private_seed"])
        )
        signature = signing_private.sign(message)
        return self._serialize(
            {
                "version": self.KEY_BUNDLE_VERSION,
                "algorithm": self.SIGNATURE_ALGORITHM,
                "signature": self._encode(signature),
            }
        )

    def verify_signature(
        self, message: bytes, signature: bytes, public_key: bytes
    ) -> bool:
        """Verify an ML-DSA-87 signature."""
        try:
            signature_data = json.loads(signature.decode("utf-8"))
            if (
                signature_data.get("version") != self.KEY_BUNDLE_VERSION
                or signature_data.get("algorithm") != self.SIGNATURE_ALGORITHM
            ):
                return False

            bundle = self._load_public_bundle(public_key)
            signing_public = MLDSA87PublicKey.from_public_bytes(
                self._decode(bundle["signature_public_key"])
            )
            signing_public.verify(
                self._decode(signature_data["signature"]),
                message,
            )
            return True
        except (
            InvalidSignature,
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            return False

    def hybrid_encryption(self, data: bytes, recipient_public_key: bytes) -> dict:
        """Encrypt data with ML-KEM-1024 and AES-256-GCM."""
        kem_ciphertext, shared_secret = self.encapsulate(recipient_public_key)
        encrypted_data = self._symmetric_encrypt(
            data,
            shared_secret,
            associated_data=kem_ciphertext,
        )
        return {
            "version": self.KEY_BUNDLE_VERSION,
            "kem_ciphertext": self._encode(kem_ciphertext),
            "encrypted_data": self._encode(encrypted_data),
            "algorithm": "ML-KEM-1024+AES-256-GCM",
        }

    def hybrid_decryption(
        self, encrypted_package: dict, private_key: bytes
    ) -> Optional[bytes]:
        """Decrypt an ML-KEM-1024 and AES-256-GCM package."""
        try:
            if (
                encrypted_package.get("version") != self.KEY_BUNDLE_VERSION
                or encrypted_package.get("algorithm")
                != "ML-KEM-1024+AES-256-GCM"
            ):
                return None

            kem_ciphertext = self._decode(encrypted_package["kem_ciphertext"])
            shared_secret = self.decapsulate(kem_ciphertext, private_key)
            if shared_secret is None:
                return None

            encrypted_data = self._decode(encrypted_package["encrypted_data"])
            return self._symmetric_decrypt(
                encrypted_data,
                shared_secret,
                associated_data=kem_ciphertext,
            )
        except (KeyError, TypeError, ValueError, InvalidTag):
            return None

    def _symmetric_encrypt(
        self, data: bytes, key: bytes, associated_data: bytes = b""
    ) -> bytes:
        nonce = secrets.token_bytes(12)
        encryption_key = self.quantum_safe_key_derivation(
            key, "orcai25-hybrid-aead-v1"
        )
        return nonce + AESGCM(encryption_key).encrypt(nonce, data, associated_data)

    def _symmetric_decrypt(
        self, data: bytes, key: bytes, associated_data: bytes = b""
    ) -> bytes:
        if len(data) < 28:
            raise ValueError("Encrypted payload is too short")
        nonce, ciphertext = data[:12], data[12:]
        encryption_key = self.quantum_safe_key_derivation(
            key, "orcai25-hybrid-aead-v1"
        )
        return AESGCM(encryption_key).decrypt(nonce, ciphertext, associated_data)

    def quantum_safe_key_derivation(
        self, master_key: bytes, context: str, length: int = 32
    ) -> bytes:
        """Derive context-bound key material with HKDF-SHA3-512."""
        if length <= 0:
            raise ValueError("Derived key length must be positive")
        return HKDF(
            algorithm=hashes.SHA3_512(),
            length=length,
            salt=None,
            info=context.encode("utf-8"),
        ).derive(master_key)

    def _load_public_bundle(self, serialized: bytes) -> Dict[str, object]:
        return self._load_bundle(
            serialized,
            required_fields=("kem_public_key", "signature_public_key"),
        )

    def _load_private_bundle(self, serialized: bytes) -> Dict[str, object]:
        return self._load_bundle(
            serialized,
            required_fields=("kem_private_seed", "signature_private_seed"),
        )

    def _load_bundle(
        self, serialized: bytes, required_fields: Tuple[str, ...]
    ) -> Dict[str, object]:
        try:
            bundle = json.loads(serialized.decode("utf-8"))
        except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid key bundle") from exc

        if (
            not isinstance(bundle, dict)
            or bundle.get("version") != self.KEY_BUNDLE_VERSION
            or bundle.get("kem_algorithm") != self.KEM_ALGORITHM
            or bundle.get("signature_algorithm") != self.SIGNATURE_ALGORITHM
            or any(field not in bundle for field in required_fields)
        ):
            raise ValueError("Unsupported or incomplete key bundle")
        return bundle

    @staticmethod
    def _serialize(value: Dict[str, object]) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.b64encode(value).decode("ascii")

    @staticmethod
    def _decode(value: object) -> bytes:
        if not isinstance(value, str):
            raise ValueError("Expected base64-encoded key material")
        try:
            return base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Invalid base64-encoded key material") from exc
