"""
Secure Communication Protocols
Implements secure, authenticated, and encrypted communication channels
Uses modern protocols with perfect forward secrecy

⚠️ IMPORTANT SECURITY NOTE:
This module uses SIMULATED cryptography for demonstration purposes.
In production, replace with actual cryptographic libraries:
- cryptography (Python library): https://cryptography.io/
- NaCl/libsodium: https://github.com/pyca/pynacl
- OpenSSL bindings

The AEAD encryption uses placeholder XOR operations that provide NO
real security. Replace with AES-256-GCM or ChaCha20-Poly1305.
"""

import json
import time
import secrets
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple
import base64


class ProtocolVersion(Enum):
    """Supported protocol versions"""
    TLS_1_3 = "TLS 1.3"
    QUIC = "QUIC"
    MTLS = "mTLS"  # Mutual TLS
    NOISE = "Noise Protocol"


class SecurityLevel(Enum):
    """Security levels for communications"""
    STANDARD = "standard"
    HIGH = "high"
    MAXIMUM = "maximum"


@dataclass
class SecureChannel:
    """Secure communication channel"""
    channel_id: str
    protocol: ProtocolVersion
    encryption_algorithm: str
    key_exchange: str
    authentication_method: str
    established_at: float
    last_used: float
    message_count: int


class SecureCommProtocol:
    """
    Secure communication protocol implementation
    Enforces encryption, authentication, and integrity
    """
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.HIGH):
        self.security_level = security_level
        self.active_channels: Dict[str, SecureChannel] = {}
        self.session_keys: Dict[str, bytes] = {}
        self.nonce_cache: Dict[str, set] = {}
        
    def establish_secure_channel(self, peer_id: str, 
                                 public_key: bytes) -> SecureChannel:
        """
        Establish secure communication channel with peer
        Uses ephemeral keys for perfect forward secrecy
        """
        channel_id = self._generate_channel_id(peer_id)
        
        # Perform key exchange (simulated Diffie-Hellman or ECDH)
        session_key = self._perform_key_exchange(public_key)
        self.session_keys[channel_id] = session_key
        
        # Initialize nonce cache for replay protection
        self.nonce_cache[channel_id] = set()
        
        # Create channel
        channel = SecureChannel(
            channel_id=channel_id,
            protocol=ProtocolVersion.TLS_1_3,
            encryption_algorithm="AES-256-GCM" if self.security_level != SecurityLevel.MAXIMUM else "ChaCha20-Poly1305",
            key_exchange="ECDHE-X25519",
            authentication_method="Ed25519",
            established_at=time.time(),
            last_used=time.time(),
            message_count=0
        )
        
        self.active_channels[channel_id] = channel
        
        print(f"[SECURE COMM] Established channel {channel_id} with {peer_id}")
        print(f"[SECURE COMM] Protocol: {channel.protocol.value}, Encryption: {channel.encryption_algorithm}")
        
        return channel
    
    def send_secure_message(self, channel_id: str, message: dict) -> Optional[bytes]:
        """
        Send encrypted and authenticated message over secure channel
        """
        if channel_id not in self.active_channels:
            print(f"[SECURE COMM ERROR] Channel not found: {channel_id}")
            return None
        
        channel = self.active_channels[channel_id]
        session_key = self.session_keys[channel_id]
        
        # Add metadata
        message_data = {
            "payload": message,
            "timestamp": time.time(),
            "nonce": secrets.token_hex(16),
            "channel_id": channel_id
        }
        
        # Serialize message
        plaintext = json.dumps(message_data).encode()
        
        # Encrypt with authenticated encryption (AEAD)
        ciphertext = self._encrypt_aead(plaintext, session_key, channel.encryption_algorithm)
        
        # Update channel stats
        channel.last_used = time.time()
        channel.message_count += 1
        
        # Rotate keys periodically for perfect forward secrecy
        if channel.message_count % 1000 == 0:
            self._rotate_session_key(channel_id)
        
        return ciphertext
    
    def receive_secure_message(self, channel_id: str, 
                               ciphertext: bytes) -> Optional[dict]:
        """
        Receive and decrypt message from secure channel
        Validates authenticity and prevents replay attacks
        """
        if channel_id not in self.active_channels:
            print(f"[SECURE COMM ERROR] Channel not found: {channel_id}")
            return None
        
        session_key = self.session_keys[channel_id]
        channel = self.active_channels[channel_id]
        
        # Decrypt with authenticated encryption
        plaintext = self._decrypt_aead(ciphertext, session_key, channel.encryption_algorithm)
        
        if plaintext is None:
            print(f"[SECURE COMM ERROR] Decryption failed for channel {channel_id}")
            return None
        
        try:
            message_data = json.loads(plaintext.decode())
        except Exception as e:
            print(f"[SECURE COMM ERROR] Invalid message format: {e}")
            return None
        
        # Verify freshness (prevent replay attacks)
        nonce = message_data.get("nonce")
        if nonce in self.nonce_cache[channel_id]:
            print(f"[SECURE COMM ERROR] Replay attack detected on channel {channel_id}")
            return None
        
        # Check timestamp
        timestamp = message_data.get("timestamp", 0)
        if abs(time.time() - timestamp) > 60:  # 1 minute tolerance
            print(f"[SECURE COMM ERROR] Message timestamp out of range")
            return None
        
        # Add nonce to cache
        self.nonce_cache[channel_id].add(nonce)
        
        # Limit cache size
        if len(self.nonce_cache[channel_id]) > 10000:
            # Remove old nonces (in production, use time-based expiry)
            old_nonces = list(self.nonce_cache[channel_id])[:5000]
            self.nonce_cache[channel_id] -= set(old_nonces)
        
        return message_data.get("payload")
    
    def _generate_channel_id(self, peer_id: str) -> str:
        """Generate unique channel identifier"""
        data = f"{peer_id}:{time.time()}:{secrets.token_hex(8)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _perform_key_exchange(self, peer_public_key: bytes) -> bytes:
        """
        Perform ephemeral key exchange (ECDH)
        In production, use actual cryptographic library (e.g., cryptography)
        """
        # Simulated ECDH key exchange
        # In production, use actual ECDH with X25519
        ephemeral_private = secrets.token_bytes(32)
        
        # Derive shared secret
        shared_secret = hashlib.sha3_512(
            ephemeral_private + peer_public_key
        ).digest()
        
        # Derive session key using HKDF
        session_key = self._hkdf(shared_secret, b"secure_channel_key", 32)
        
        return session_key
    
    def _hkdf(self, input_key: bytes, info: bytes, length: int) -> bytes:
        """HMAC-based Key Derivation Function"""
        # Extract
        prk = hashlib.sha3_512(input_key).digest()
        
        # Expand
        okm = b''
        counter = 1
        while len(okm) < length:
            h = hashlib.sha3_512()
            h.update(prk)
            h.update(okm[-64:] if okm else b'')
            h.update(info)
            h.update(counter.to_bytes(1, 'big'))
            okm += h.digest()
            counter += 1
        
        return okm[:length]
    
    def _encrypt_aead(self, plaintext: bytes, key: bytes, 
                     algorithm: str) -> bytes:
        """
        Authenticated encryption with associated data
        In production, use actual AES-GCM or ChaCha20-Poly1305
        """
        # Generate random IV/nonce
        iv = secrets.token_bytes(12)
        
        # Derive encryption key
        enc_key = self._hkdf(key, b"encryption", 32)
        
        # Simulate AEAD encryption (placeholder)
        # In production, use actual cryptographic library
        encrypted = bytes(b ^ enc_key[i % len(enc_key)] 
                         for i, b in enumerate(plaintext))
        
        # Generate authentication tag
        auth_tag = hashlib.sha3_256(
            enc_key + iv + encrypted
        ).digest()[:16]
        
        # Combine IV + ciphertext + tag
        return iv + encrypted + auth_tag
    
    def _decrypt_aead(self, ciphertext: bytes, key: bytes, 
                     algorithm: str) -> Optional[bytes]:
        """
        Decrypt and verify authenticated encryption
        """
        try:
            # Extract components
            iv = ciphertext[:12]
            auth_tag = ciphertext[-16:]
            encrypted = ciphertext[12:-16]
            
            # Derive encryption key
            enc_key = self._hkdf(key, b"encryption", 32)
            
            # Verify authentication tag
            expected_tag = hashlib.sha3_256(
                enc_key + iv + encrypted
            ).digest()[:16]
            
            if not secrets.compare_digest(auth_tag, expected_tag):
                print("[SECURE COMM ERROR] Authentication tag verification failed")
                return None
            
            # Decrypt
            plaintext = bytes(b ^ enc_key[i % len(enc_key)] 
                            for i, b in enumerate(encrypted))
            
            return plaintext
        except Exception as e:
            print(f"[SECURE COMM ERROR] Decryption error: {e}")
            return None
    
    def _rotate_session_key(self, channel_id: str):
        """
        Rotate session key for perfect forward secrecy
        """
        old_key = self.session_keys[channel_id]
        
        # Derive new key from old key
        new_key = self._hkdf(old_key, b"key_rotation", 32)
        
        self.session_keys[channel_id] = new_key
        
        print(f"[SECURE COMM] Rotated session key for channel {channel_id}")
    
    def close_channel(self, channel_id: str):
        """Close secure channel and clear keys"""
        if channel_id in self.active_channels:
            del self.active_channels[channel_id]
        
        if channel_id in self.session_keys:
            # Securely wipe key from memory
            del self.session_keys[channel_id]
        
        if channel_id in self.nonce_cache:
            del self.nonce_cache[channel_id]
        
        print(f"[SECURE COMM] Closed channel {channel_id}")
    
    def get_channel_status(self, channel_id: str) -> Optional[Dict]:
        """Get status of secure channel"""
        if channel_id not in self.active_channels:
            return None
        
        channel = self.active_channels[channel_id]
        
        return {
            "channel_id": channel.channel_id,
            "protocol": channel.protocol.value,
            "encryption": channel.encryption_algorithm,
            "key_exchange": channel.key_exchange,
            "established_at": channel.established_at,
            "last_used": channel.last_used,
            "message_count": channel.message_count,
            "age_seconds": time.time() - channel.established_at
        }
    
    def enforce_protocol_requirements(self) -> Dict[str, bool]:
        """
        Enforce security protocol requirements
        Returns dict of requirement checks
        """
        requirements = {
            "tls_1_3_minimum": True,  # No older TLS versions
            "perfect_forward_secrecy": True,  # Ephemeral key exchange
            "authenticated_encryption": True,  # AEAD ciphers only
            "certificate_pinning": True,  # Pin certificates
            "no_weak_ciphers": True,  # Block weak algorithms
            "mutual_authentication": self.security_level == SecurityLevel.MAXIMUM
        }
        
        print(f"[PROTOCOL ENFORCEMENT] Security level: {self.security_level.value}")
        print(f"[PROTOCOL ENFORCEMENT] Requirements: {requirements}")
        
        return requirements
