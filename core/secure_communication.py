"""
Authenticated application-message encryption.

This module provides an application-level secure envelope using X25519 key
agreement and modern AEAD ciphers. Transport TLS and peer-key authentication
remain deployment responsibilities.
"""

import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class ProtocolVersion(Enum):
    """Supported protocol identifiers."""

    SECURE_ENVELOPE_V1 = "Secure Envelope v1"
    TLS_1_3 = "TLS 1.3"
    QUIC = "QUIC"
    MTLS = "mTLS"
    NOISE = "Noise Protocol"


class SecurityLevel(Enum):
    """Security levels for communications."""

    STANDARD = "standard"
    HIGH = "high"
    MAXIMUM = "maximum"


@dataclass
class SecureChannel:
    """Secure communication channel metadata."""

    channel_id: str
    protocol: ProtocolVersion
    encryption_algorithm: str
    key_exchange: str
    authentication_method: str
    local_public_key: bytes
    established_at: float
    last_used: float
    message_count: int


class SecureCommProtocol:
    """Encrypts authenticated messages and rejects stale or replayed payloads."""

    def __init__(self, security_level: SecurityLevel = SecurityLevel.HIGH):
        self.security_level = security_level
        self.active_channels: Dict[str, SecureChannel] = {}
        self.session_keys: Dict[str, bytes] = {}
        self.nonce_cache: Dict[str, set] = {}

    def establish_secure_channel(
        self, peer_id: str, public_key: bytes
    ) -> SecureChannel:
        """
        Establish a channel using a pre-validated X25519 peer public key.

        ``local_public_key`` on the returned channel must be sent to the peer
        through an authenticated handshake.
        """
        channel_id = self._generate_channel_id(peer_id)
        session_key, local_public_key = self._perform_key_exchange(public_key)
        self.session_keys[channel_id] = session_key
        self.nonce_cache[channel_id] = set()

        algorithm = (
            "ChaCha20-Poly1305"
            if self.security_level == SecurityLevel.MAXIMUM
            else "AES-256-GCM"
        )
        now = time.time()
        channel = SecureChannel(
            channel_id=channel_id,
            protocol=ProtocolVersion.SECURE_ENVELOPE_V1,
            encryption_algorithm=algorithm,
            key_exchange="X25519",
            authentication_method="pre-validated peer public key",
            local_public_key=local_public_key,
            established_at=now,
            last_used=now,
            message_count=0,
        )
        self.active_channels[channel_id] = channel

        print(f"[SECURE COMM] Established channel {channel_id} with {peer_id}")
        print(
            f"[SECURE COMM] Protocol: {channel.protocol.value}, "
            f"Encryption: {channel.encryption_algorithm}"
        )
        return channel

    def send_secure_message(self, channel_id: str, message: dict) -> Optional[bytes]:
        """Serialize and encrypt a message for an active channel."""
        if channel_id not in self.active_channels:
            print(f"[SECURE COMM ERROR] Channel not found: {channel_id}")
            return None

        channel = self.active_channels[channel_id]
        message_data = {
            "payload": message,
            "timestamp": time.time(),
            "nonce": secrets.token_hex(16),
            "channel_id": channel_id,
        }
        plaintext = json.dumps(
            message_data, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        ciphertext = self._encrypt_aead(
            plaintext,
            self.session_keys[channel_id],
            channel.encryption_algorithm,
        )

        channel.last_used = time.time()
        channel.message_count += 1
        if channel.message_count % 1000 == 0:
            self._rotate_session_key(channel_id)
        return ciphertext

    def receive_secure_message(
        self, channel_id: str, ciphertext: bytes
    ) -> Optional[dict]:
        """Decrypt a message and enforce channel binding, freshness, and replay checks."""
        if channel_id not in self.active_channels:
            print(f"[SECURE COMM ERROR] Channel not found: {channel_id}")
            return None

        channel = self.active_channels[channel_id]
        plaintext = self._decrypt_aead(
            ciphertext,
            self.session_keys[channel_id],
            channel.encryption_algorithm,
        )
        if plaintext is None:
            print(f"[SECURE COMM ERROR] Decryption failed for channel {channel_id}")
            return None

        try:
            message_data = json.loads(plaintext.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"[SECURE COMM ERROR] Invalid message format: {exc}")
            return None

        if (
            not isinstance(message_data, dict)
            or message_data.get("channel_id") != channel_id
        ):
            print("[SECURE COMM ERROR] Message channel binding is invalid")
            return None

        nonce = message_data.get("nonce")
        if not isinstance(nonce, str) or not nonce:
            print("[SECURE COMM ERROR] Message nonce is invalid")
            return None
        if nonce in self.nonce_cache[channel_id]:
            print(f"[SECURE COMM ERROR] Replay attack detected on channel {channel_id}")
            return None

        timestamp = message_data.get("timestamp")
        if not isinstance(timestamp, (int, float)) or abs(time.time() - timestamp) > 60:
            print("[SECURE COMM ERROR] Message timestamp out of range")
            return None

        self.nonce_cache[channel_id].add(nonce)
        if len(self.nonce_cache[channel_id]) > 10000:
            old_nonces = list(self.nonce_cache[channel_id])[:5000]
            self.nonce_cache[channel_id].difference_update(old_nonces)
        return message_data.get("payload")

    def _generate_channel_id(self, peer_id: str) -> str:
        data = f"{peer_id}:{time.time()}:{secrets.token_hex(8)}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]

    def _perform_key_exchange(self, peer_public_key: bytes) -> Tuple[bytes, bytes]:
        peer_key = x25519.X25519PublicKey.from_public_bytes(peer_public_key)
        ephemeral_private = x25519.X25519PrivateKey.generate()
        shared_secret = ephemeral_private.exchange(peer_key)
        local_public_key = ephemeral_private.public_key().public_bytes_raw()
        session_key = self._hkdf(shared_secret, b"orcai25-secure-channel-v1", 32)
        return session_key, local_public_key

    def _hkdf(self, input_key: bytes, info: bytes, length: int) -> bytes:
        return HKDF(
            algorithm=hashes.SHA3_512(),
            length=length,
            salt=None,
            info=info,
        ).derive(input_key)

    def _encrypt_aead(self, plaintext: bytes, key: bytes, algorithm: str) -> bytes:
        nonce = secrets.token_bytes(12)
        aead = self._get_aead(key, algorithm)
        return nonce + aead.encrypt(nonce, plaintext, None)

    def _decrypt_aead(
        self, ciphertext: bytes, key: bytes, algorithm: str
    ) -> Optional[bytes]:
        if len(ciphertext) < 28:
            return None
        nonce, encrypted = ciphertext[:12], ciphertext[12:]
        try:
            return self._get_aead(key, algorithm).decrypt(
                nonce, encrypted, None
            )
        except (InvalidTag, ValueError):
            return None

    def _get_aead(self, key: bytes, algorithm: str):
        encryption_key = self._hkdf(
            key,
            f"orcai25:{algorithm}:v1".encode("ascii"),
            32,
        )
        if algorithm == "AES-256-GCM":
            return AESGCM(encryption_key)
        if algorithm == "ChaCha20-Poly1305":
            return ChaCha20Poly1305(encryption_key)
        raise ValueError(f"Unsupported encryption algorithm: {algorithm}")

    def _rotate_session_key(self, channel_id: str):
        old_key = self.session_keys[channel_id]
        self.session_keys[channel_id] = self._hkdf(
            old_key, b"orcai25-key-rotation-v1", 32
        )
        print(f"[SECURE COMM] Rotated session key for channel {channel_id}")

    def close_channel(self, channel_id: str):
        """Close a channel and discard its in-memory key material."""
        self.active_channels.pop(channel_id, None)
        self.session_keys.pop(channel_id, None)
        self.nonce_cache.pop(channel_id, None)
        print(f"[SECURE COMM] Closed channel {channel_id}")

    def get_channel_status(self, channel_id: str) -> Optional[Dict]:
        if channel_id not in self.active_channels:
            return None
        channel = self.active_channels[channel_id]
        return {
            "channel_id": channel.channel_id,
            "protocol": channel.protocol.value,
            "encryption": channel.encryption_algorithm,
            "key_exchange": channel.key_exchange,
            "authentication": channel.authentication_method,
            "established_at": channel.established_at,
            "last_used": channel.last_used,
            "message_count": channel.message_count,
            "age_seconds": time.time() - channel.established_at,
        }

    def enforce_protocol_requirements(self) -> Dict[str, bool]:
        """
        Report application-envelope controls.

        TLS, certificate pinning, and mutual authentication must be enforced by
        the deployment's transport layer.
        """
        requirements = {
            "application_aead": True,
            "x25519_ephemeral_key_exchange": True,
            "replay_protection": True,
            "transport_tls_1_3": False,
            "certificate_pinning": False,
            "mutual_authentication": False,
        }
        print(f"[PROTOCOL ENFORCEMENT] Security level: {self.security_level.value}")
        print(f"[PROTOCOL ENFORCEMENT] Requirements: {requirements}")
        return requirements
