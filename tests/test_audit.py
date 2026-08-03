import unittest

from audit.compliance_framework import AuditEventType, AuditLogger


class AuditLoggerTests(unittest.TestCase):
    def test_integrity_verification_detects_tampering(self):
        logger = AuditLogger("test-secret")
        entry = logger.log_event(
            AuditEventType.ACCESS,
            actor="tester",
            resource="record",
            action="read",
            result="success",
        )
        self.assertTrue(logger.verify_integrity())

        entry.result = "failure"
        self.assertFalse(logger.verify_integrity())


if __name__ == "__main__":
    unittest.main()
