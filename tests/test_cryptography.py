import copy
import unittest

from cryptography.hazmat.primitives.asymmetric import x25519

from core.quantum_resistant_crypto import QuantumResistantCrypto
from core.secure_communication import SecureCommProtocol, SecurityLevel


class QuantumResistantCryptoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.crypto = QuantumResistantCrypto()
        cls.public_key, cls.private_key = cls.crypto.generate_keypair()

    def test_kem_round_trip(self):
        ciphertext, expected_secret = self.crypto.encapsulate(self.public_key)
        self.assertEqual(
            self.crypto.decapsulate(ciphertext, self.private_key),
            expected_secret,
        )

    def test_signature_verification_and_tampering(self):
        message = b"authenticated message"
        signature = self.crypto.hash_based_signature(message, self.private_key)

        self.assertTrue(
            self.crypto.verify_signature(message, signature, self.public_key)
        )
        self.assertFalse(
            self.crypto.verify_signature(
                message + b"!",
                signature,
                self.public_key,
            )
        )
        self.assertFalse(
            self.crypto.verify_signature(message, b"[]", self.public_key)
        )

    def test_hybrid_encryption_round_trip_and_tampering(self):
        plaintext = b"classified payload"
        package = self.crypto.hybrid_encryption(plaintext, self.public_key)

        self.assertEqual(
            self.crypto.hybrid_decryption(package, self.private_key),
            plaintext,
        )

        tampered = copy.deepcopy(package)
        tampered["encrypted_data"] = tampered["encrypted_data"][:-4] + "AAAA"
        self.assertIsNone(
            self.crypto.hybrid_decryption(tampered, self.private_key)
        )


class SecureCommunicationTests(unittest.TestCase):
    def _new_channel(self, level=SecurityLevel.HIGH):
        protocol = SecureCommProtocol(level)
        peer_public_key = (
            x25519.X25519PrivateKey.generate().public_key().public_bytes_raw()
        )
        channel = protocol.establish_secure_channel("peer", peer_public_key)
        return protocol, channel

    def test_message_round_trip_and_replay_rejection(self):
        protocol, channel = self._new_channel()
        ciphertext = protocol.send_secure_message(
            channel.channel_id, {"status": "ok"}
        )

        self.assertEqual(
            protocol.receive_secure_message(channel.channel_id, ciphertext),
            {"status": "ok"},
        )
        self.assertIsNone(
            protocol.receive_secure_message(channel.channel_id, ciphertext)
        )

    def test_tampered_ciphertext_is_rejected(self):
        protocol, channel = self._new_channel(SecurityLevel.MAXIMUM)
        ciphertext = protocol.send_secure_message(
            channel.channel_id, {"status": "ok"}
        )
        tampered = ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])

        self.assertIsNone(
            protocol.receive_secure_message(channel.channel_id, tampered)
        )

    def test_invalid_peer_key_is_rejected(self):
        protocol = SecureCommProtocol()
        with self.assertRaises(ValueError):
            protocol.establish_secure_channel("peer", b"invalid")


if __name__ == "__main__":
    unittest.main()
