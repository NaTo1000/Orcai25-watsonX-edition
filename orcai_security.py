"""
Orcai25 WatsonX Edition - Enterprise Cybersecurity Stack
Main initialization and orchestration module
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.asymmetric import x25519

# Import core security modules
sys.path.insert(0, str(Path(__file__).parent))

from core.zero_trust_architecture import ZeroTrustEngine, SecurityContext, TrustLevel
from core.quantum_resistant_crypto import QuantumResistantCrypto
from core.ai_threat_detection import AIThreatDetector
from core.secure_communication import SecureCommProtocol, SecurityLevel
from emergency_protocols.rogue_ai_containment import RogueAIDetector
from audit.compliance_framework import AuditLogger, ComplianceChecker, AuditEventType, ComplianceStandard
from monitoring.security_monitor import SecurityMonitor, AlertSeverity


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "security_config.json"
VERSION = "1.0.0"


class OrcaiSecurityStack:
    """
    Main Orcai25 Cybersecurity Stack
    Orchestrates all security components for comprehensive protection
    """
    
    def __init__(self, config_path: Optional[str] = None):
        print("=" * 80)
        print("ORCAI25 WATSONX EDITION - ENTERPRISE CYBERSECURITY STACK")
        print("Next-Generation Security for AI Systems")
        print("=" * 80)
        
        # Load configuration
        resolved_config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self.config = self._load_config(resolved_config_path)
        
        # Initialize components
        print("\n[INIT] Initializing security components...")
        
        # Core security
        self.zero_trust = ZeroTrustEngine(secret_key=self._get_secret_key())
        print("✓ Zero Trust Architecture initialized")
        
        self.quantum_crypto = QuantumResistantCrypto()
        print("✓ Quantum-Resistant Cryptography initialized")
        
        self.ai_threat_detector = AIThreatDetector()
        print("✓ AI Threat Detection System initialized")
        
        # Communication security
        security_level = SecurityLevel[self.config["communication"]["security_level"].upper()]
        self.secure_comm = SecureCommProtocol(security_level=security_level)
        print("✓ Secure Communication Protocol initialized")
        
        # Emergency protocols
        self.rogue_ai_detector = RogueAIDetector()
        print("✓ Rogue AI Containment System initialized")
        
        # Audit and compliance
        self.audit_logger = AuditLogger(secret_key=self._get_secret_key())
        self.compliance_checker = ComplianceChecker(self.audit_logger)
        print("✓ Audit and Compliance Framework initialized")
        
        # Monitoring
        self.security_monitor = SecurityMonitor()
        print("✓ Security Monitoring System initialized")
        
        # Register emergency alert handlers
        self._setup_alert_handlers()
        
        print("\n[INIT] All security components initialized successfully")
        print("=" * 80)
        
        # Log initialization
        self.audit_logger.log_event(
            AuditEventType.SECURITY_EVENT,
            actor="system",
            resource="orcai_security_stack",
            action="initialize",
            result="success",
            details={"version": VERSION, "components": 7}
        )
    
    def _load_config(self, config_path: Path) -> dict:
        """Load security configuration"""
        try:
            with config_path.open("r", encoding="utf-8") as f:
                config = json.load(f)
            print(f"✓ Configuration loaded from {config_path}")
            return config
        except FileNotFoundError:
            print(f"⚠ Config file not found: {config_path}, using defaults")
            return self._get_default_config()
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON configuration: {config_path}") from exc
    
    def _get_default_config(self) -> dict:
        """Get default configuration"""
        return {
            "security": {
                "encryption": {"enabled": True},
                "access_controls": {"enabled": True},
            },
            "monitoring": {"enabled": True},
            "audit": {"enabled": True},
            "emergency_protocols": {"enabled": True},
            "communication": {"security_level": "high"},
            "compliance": {
                "intrusion_detection_enabled": True,
                "breach_notification_enabled": True,
                "privacy_by_design": True,
                "user_management_enabled": True,
            },
        }
    
    def _get_secret_key(self) -> str:
        """Get secret key for cryptographic operations"""
        # In production, load from secure key management system (e.g., AWS KMS, HashiCorp Vault)
        import secrets
        return secrets.token_hex(32)
    
    def _setup_alert_handlers(self):
        """Setup alert handlers for different severity levels"""
        
        def critical_alert_handler(alert):
            print(f"\n{'!' * 80}")
            print(f"CRITICAL ALERT: {alert.title}")
            print(f"{'!' * 80}\n")
            # In production, trigger paging, escalation, etc.
        
        def high_alert_handler(alert):
            print(f"\n⚠ HIGH SEVERITY ALERT: {alert.title}")
            # In production, notify security team
        
        self.security_monitor.register_alert_handler(
            AlertSeverity.CRITICAL, critical_alert_handler
        )
        self.security_monitor.register_alert_handler(
            AlertSeverity.HIGH, high_alert_handler
        )
    
    def run_compliance_audit(self) -> dict:
        """
        Run comprehensive compliance audit
        """
        print("\n" + "=" * 80)
        print("RUNNING COMPLIANCE AUDIT")
        print("=" * 80 + "\n")
        
        system_config = {
            "encryption_enabled": self.config["security"]["encryption"]["enabled"],
            "access_controls_enabled": self.config["security"]["access_controls"]["enabled"],
            "audit_logging_enabled": self.config["audit"]["enabled"],
            "intrusion_detection_enabled": self.config["compliance"]["intrusion_detection_enabled"],
            "breach_notification_enabled": self.config["compliance"]["breach_notification_enabled"],
            "privacy_by_design": self.config["compliance"]["privacy_by_design"],
            "user_management_enabled": self.config["compliance"]["user_management_enabled"]
        }
        
        results = {}
        
        # Check each compliance standard
        for standard in [ComplianceStandard.SOC2, ComplianceStandard.ISO27001, 
                        ComplianceStandard.GDPR, ComplianceStandard.HIPAA]:
            report = self.compliance_checker.check_compliance(standard, system_config)
            results[standard.value] = report
            
            print(f"\n{standard.value}:")
            print(f"  Compliance Score: {report['compliance_score']:.1%}")
            print(f"  Passed Checks: {report['passed']}/{report['total_rules_checked']}")
            print(f"  Violations: {report['violations']}")
            
            if report['violations'] > 0:
                print(f"  ⚠ Violations found:")
                for violation in report['violation_details']:
                    print(f"    - {violation['rule_id']}: {violation['description']}")
        
        print("\n" + "=" * 80)
        
        return results
    
    def run_security_health_check(self) -> dict:
        """
        Run comprehensive security health check
        """
        print("\n" + "=" * 80)
        print("SECURITY HEALTH CHECK")
        print("=" * 80 + "\n")
        
        system_config = {
            "encryption_enabled": self.config["security"]["encryption"]["enabled"],
            "access_controls_enabled": self.config["security"]["access_controls"]["enabled"],
            "audit_logging_enabled": self.config["audit"]["enabled"],
            "intrusion_detection_enabled": self.config["compliance"]["intrusion_detection_enabled"]
        }
        
        health = self.security_monitor.run_health_check(system_config)
        
        print(f"Overall Status: {health['overall_status'].upper()}")
        print("\nComponent Checks:")
        for check_name, check_result in health['checks'].items():
            status_icon = "✓" if check_result['status'] == 'pass' else "✗"
            critical_text = " [CRITICAL]" if check_result.get('critical') else ""
            print(f"  {status_icon} {check_name}: {check_result['status']}{critical_text}")
        
        print("\n" + "=" * 80)
        
        return health
    
    def demonstrate_capabilities(self):
        """
        Demonstrate key security capabilities
        """
        print("\n" + "=" * 80)
        print("DEMONSTRATING SECURITY CAPABILITIES")
        print("=" * 80 + "\n")
        
        # 1. Zero Trust Verification
        print("1. ZERO TRUST ARCHITECTURE")
        print("-" * 40)
        token = self.zero_trust.generate_secure_token("user123")
        context = SecurityContext(
            user_id="user123",
            device_id="device456",
            ip_address="192.168.1.100",
            timestamp=__import__('time').time(),
            session_token=token,
            trust_level=TrustLevel.HIGH,
            mfa_verified=True,
            behavioral_score=0.8
        )
        status = self.zero_trust.verify_request(context)
        print(f"  Request verification: {status.value}")
        print(f"  Trust level: {context.trust_level.name}")
        print(f"  MFA verified: {context.mfa_verified}")
        
        # 2. Quantum-Resistant Crypto
        print("\n2. QUANTUM-RESISTANT CRYPTOGRAPHY")
        print("-" * 40)
        pub_key, priv_key = self.quantum_crypto.generate_keypair()
        print(f"  Key pair generated (algorithm: {self.quantum_crypto.algorithm})")
        message = b"Classified information"
        signature = self.quantum_crypto.hash_based_signature(message, priv_key)
        verified = self.quantum_crypto.verify_signature(message, signature, pub_key)
        print(f"  Digital signature verified: {verified}")
        
        # 3. AI Threat Detection
        print("\n3. AI THREAT DETECTION")
        print("-" * 40)
        behavior_data = {
            "input_variance": 0.9,
            "cpu_usage": 0.95,
            "unauthorized_access_attempts": 2
        }
        threat = self.ai_threat_detector.analyze_behavior("ai_system_1", behavior_data)
        print(f"  Threat level: {threat.threat_level.name}")
        print(f"  Behavior type: {threat.behavior_type.value}")
        print(f"  Confidence: {threat.confidence_score:.2%}")
        print(f"  Indicators: {', '.join(threat.indicators)}")
        
        # 4. Emergency Containment
        print("\n4. EMERGENCY AI CONTAINMENT")
        print("-" * 40)
        
        def mock_kill_switch():
            print("    [Kill switch executed]")
        
        self.rogue_ai_detector.register_system("ai_system_1", mock_kill_switch)
        rogue_metrics = {
            "safety_check_bypasses": 1,
            "goal_adherence_score": 0.3
        }
        is_rogue = self.rogue_ai_detector.check_for_rogue_behavior("ai_system_1", rogue_metrics)
        print(f"  Rogue behavior detected: {is_rogue}")
        print(f"  Emergency level: {self.rogue_ai_detector.emergency_level.name}")
        
        # 5. Audit Logging
        print("\n5. AUDIT AND COMPLIANCE")
        print("-" * 40)
        self.audit_logger.log_event(
            AuditEventType.ACCESS,
            actor="admin_user",
            resource="classified_database",
            action="read",
            result="success",
            details={"records_accessed": 10}
        )
        integrity_ok = self.audit_logger.verify_integrity()
        print(f"  Audit log integrity verified: {integrity_ok}")
        print(f"  Total audit entries: {len(self.audit_logger.audit_log)}")
        
        # 6. Secure Communication
        print("\n6. SECURE COMMUNICATION")
        print("-" * 40)
        peer_pub_key = (
            x25519.X25519PrivateKey.generate().public_key().public_bytes_raw()
        )
        channel = self.secure_comm.establish_secure_channel("peer123", peer_pub_key)
        print(f"  Channel established: {channel.channel_id}")
        print(f"  Protocol: {channel.protocol.value}")
        print(f"  Encryption: {channel.encryption_algorithm}")
        
        print("\n" + "=" * 80)


def main(argv=None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Orcai25 security stack")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("all", "demo", "health", "compliance"),
        default="all",
    )
    parser.add_argument("--config", help="Path to a security configuration file")
    args = parser.parse_args(argv)

    stack = OrcaiSecurityStack(args.config)

    if args.command in ("all", "demo"):
        stack.demonstrate_capabilities()

    exit_code = 0
    if args.command in ("all", "health"):
        health = stack.run_security_health_check()
        if health["overall_status"] != "healthy":
            exit_code = 1

    if args.command in ("all", "compliance"):
        compliance = stack.run_compliance_audit()
        if any(report["violations"] for report in compliance.values()):
            exit_code = 1

    print("\n" + "=" * 80)
    print("ORCAI25 SECURITY STACK CHECKS COMPLETE")
    print("=" * 80 + "\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
