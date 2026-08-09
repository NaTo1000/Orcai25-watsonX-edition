import io
import time
import unittest
from contextlib import redirect_stdout

from core.ai_threat_detection import ThreatLevel
from core.quantum_resistant_crypto import QuantumResistantCrypto
from core.zero_trust_architecture import (
    SecurityContext,
    TrustLevel,
    VerificationStatus,
)
from orcai_security import OrcaiSecurityStack


class SecurityIntegrationTests(unittest.TestCase):
    def create_stack(self):
        with redirect_stdout(io.StringIO()):
            return OrcaiSecurityStack()

    def test_invalid_access_reaches_audit_and_monitoring(self):
        stack = self.create_stack()
        context = SecurityContext(
            user_id="intruder",
            device_id="unknown",
            ip_address="203.0.113.10",
            timestamp=time.time(),
            session_token="invalid",
            trust_level=TrustLevel.MEDIUM,
            mfa_verified=False,
            behavioral_score=1.0,
        )

        with redirect_stdout(io.StringIO()):
            status = stack.verify_access(context)

        self.assertEqual(status, VerificationStatus.FAILED)
        self.assertTrue(stack.audit_logger.verify_integrity())
        self.assertTrue(stack.security_monitor.active_alerts)
        event_types = [
            event.event_type for event in stack.event_bus.recent_events()
        ]
        self.assertIn("zero_trust.invalid_token", event_types)
        self.assertIn("monitoring.alert_raised", event_types)

    def test_ai_threat_reaches_containment(self):
        stack = self.create_stack()
        stack.register_ai_system("model-1", lambda: None)

        with redirect_stdout(io.StringIO()):
            threat = stack.analyze_ai_behavior(
                "model-1",
                {
                    "data_access_rate": 2001,
                    "unauthorized_access_attempts": 1,
                },
            )

        self.assertEqual(threat.threat_level, ThreatLevel.CRITICAL)
        self.assertEqual(
            stack.rogue_ai_detector.emergency_level.name,
            "RED",
        )
        self.assertTrue(stack.rogue_ai_detector.containment_active)

    def test_simulated_crypto_interfaces_round_trip(self):
        crypto = QuantumResistantCrypto()
        public_key, private_key = crypto.generate_keypair()
        ciphertext, shared_secret = crypto.encapsulate(public_key)
        self.assertEqual(
            crypto.decapsulate(ciphertext, private_key),
            shared_secret,
        )

        signature = crypto.hash_based_signature(b"message", private_key)
        self.assertTrue(
            crypto.verify_signature(b"message", signature, public_key)
        )
        package = crypto.hybrid_encryption(b"message", public_key)
        self.assertEqual(
            crypto.hybrid_decryption(package, private_key),
            b"message",
        )

    def test_secure_message_survives_key_rotation(self):
        stack = self.create_stack()
        with redirect_stdout(io.StringIO()):
            channel = stack.establish_secure_channel("peer")
            for index in range(1001):
                ciphertext = stack.send_secure_message(
                    channel.channel_id,
                    {"index": index},
                )
                message = stack.receive_secure_message(
                    channel.channel_id,
                    ciphertext,
                )
                self.assertEqual(message, {"index": index})


if __name__ == "__main__":
    unittest.main()
