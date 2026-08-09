"""
Orcai25 WatsonX Edition - Enterprise Cybersecurity Stack
Main initialization and orchestration module
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Optional

# Import core security modules
sys.path.insert(0, str(Path(__file__).parent))

from core.zero_trust_architecture import (
    SecurityContext,
    TrustLevel,
    VerificationStatus,
    ZeroTrustEngine,
)
from core.quantum_resistant_crypto import QuantumResistantCrypto
from core.ai_threat_detection import AIThreatDetector, ThreatLevel, ThreatSignature
from core.secure_communication import (
    SecureChannel,
    SecureCommProtocol,
    SecurityLevel,
)
from core.security_events import (
    EventSeverity,
    SecurityEvent,
    SecurityEventBus,
)
from emergency_protocols.rogue_ai_containment import RogueAIDetector, EmergencyLevel
from audit.compliance_framework import AuditLogger, ComplianceChecker, AuditEventType, ComplianceStandard
from monitoring.security_monitor import (
    AlertSeverity,
    MonitoringMetric,
    SecurityAlert,
    SecurityMonitor,
    ThreatIntelligenceFeed,
)


class OrcaiSecurityStack:
    """
    Main Orcai25 Cybersecurity Stack
    Orchestrates all security components for comprehensive protection
    """
    
    def __init__(self, config_path: str = "config/security_config.json"):
        print("=" * 80)
        print("ORCAI25 WATSONX EDITION - ENTERPRISE CYBERSECURITY STACK")
        print("Next-Generation Security for AI Systems")
        print("=" * 80)
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize components
        print("\n[INIT] Initializing security components...")

        self.event_bus = SecurityEventBus()
        master_key = self._get_secret_key()

        # Audit is initialized first so every later component can use it.
        self.audit_logger = AuditLogger(secret_key=master_key)
        self.compliance_checker = ComplianceChecker(self.audit_logger)
        print("✓ Audit and Compliance Framework initialized")

        monitor_config = self.config["monitoring"]
        self.security_monitor = SecurityMonitor(
            event_bus=self.event_bus,
            baseline_samples=monitor_config["baseline_samples"],
            anomaly_detection=monitor_config["anomaly_detection"],
            alert_thresholds=monitor_config["alert_thresholds"],
        )
        print("✓ Security Monitoring System initialized")

        zero_trust_config = self.config["security"]["zero_trust"]
        self.zero_trust = ZeroTrustEngine(
            secret_key=master_key,
            event_bus=self.event_bus,
            mfa_required_for_high_trust=zero_trust_config[
                "mfa_required_for_high_trust"
            ],
            replay_window_seconds=zero_trust_config[
                "continuous_verification_interval"
            ],
            behavioral_score_threshold=zero_trust_config[
                "behavioral_score_threshold"
            ],
            session_timeout_seconds=zero_trust_config[
                "session_timeout_seconds"
            ],
        )
        print("✓ Zero Trust Architecture initialized")

        quantum_config = self.config["security"]["quantum_crypto"]
        self.quantum_crypto = QuantumResistantCrypto(
            algorithm=quantum_config["algorithm"],
            hash_algorithm=quantum_config["hash_algorithm"],
            event_bus=self.event_bus,
        )
        print("✓ Quantum-Resistant Cryptography initialized")

        self.ai_threat_detector = AIThreatDetector(event_bus=self.event_bus)
        print("✓ AI Threat Detection System initialized")

        # Communication security
        security_level = SecurityLevel[self.config["communication"]["security_level"].upper()]
        self.secure_comm = SecureCommProtocol(
            security_level=security_level,
            event_bus=self.event_bus,
            key_deriver=self.quantum_crypto.quantum_safe_key_derivation,
        )
        print("✓ Secure Communication Protocol initialized")

        # Emergency protocols
        emergency_config = self.config["emergency_protocols"]
        self.rogue_ai_detector = RogueAIDetector(
            event_bus=self.event_bus,
            emergency_contacts=emergency_config["emergency_contacts"],
            automatic_containment=emergency_config["automatic_containment"],
        )
        print("✓ Rogue AI Containment System initialized")

        self.threat_intelligence = ThreatIntelligenceFeed()
        self.event_bus.subscribe(self._route_security_event)

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
            details={"version": "1.0.0", "components": 7}
        )
    
    def _load_config(self, config_path: str) -> dict:
        """Load security configuration"""
        path = Path(config_path).expanduser()
        if not path.is_absolute() and not path.exists():
            path = Path(__file__).resolve().parent / path

        try:
            with path.open("r", encoding="utf-8") as config_file:
                loaded_config = json.load(config_file)
            if not isinstance(loaded_config, dict):
                raise ValueError("configuration root must be a JSON object")
            config = self._merge_config(
                self._get_default_config(),
                loaded_config,
            )
            print(f"✓ Configuration loaded from {path}")
            return config
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            print(f"⚠ Config unavailable ({exc}), using defaults")
            return self._get_default_config()

    @classmethod
    def _merge_config(cls, defaults: dict, overrides: dict) -> dict:
        """Recursively merge configuration values over safe defaults."""
        merged = dict(defaults)
        for key, value in overrides.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                merged[key] = cls._merge_config(merged[key], value)
            else:
                merged[key] = value
        return merged
    
    def _get_default_config(self) -> dict:
        """Get default configuration"""
        return {
            "security": {
                "zero_trust": {
                    "enabled": True,
                    "mfa_required_for_high_trust": True,
                    "session_timeout_seconds": 3600,
                    "continuous_verification_interval": 300,
                    "behavioral_score_threshold": 0.3,
                },
                "quantum_crypto": {
                    "enabled": True,
                    "algorithm": "CRYSTALS-KYBER-1024",
                    "hash_algorithm": "SHA3-512",
                },
                "encryption": {"enabled": True},
                "access_controls": {"enabled": True},
            },
            "monitoring": {
                "enabled": True,
                "anomaly_detection": True,
                "baseline_samples": 100,
                "alert_thresholds": {
                    "cpu_usage": 0.9,
                    "memory_usage": 0.9,
                    "failed_logins": 5,
                    "api_errors": 100,
                },
            },
            "audit": {"enabled": True},
            "emergency_protocols": {
                "enabled": True,
                "automatic_containment": True,
                "emergency_contacts": [],
            },
            "threat_detection": {"enabled": True},
            "compliance": {
                "intrusion_detection_enabled": True,
                "breach_notification_enabled": True,
                "privacy_by_design": True,
                "user_management_enabled": True,
            },
            "communication": {"security_level": "high"},
        }
    
    def _get_secret_key(self) -> str:
        """Get secret key for cryptographic operations"""
        import secrets
        secret_file = os.environ.get("ORCAI_SECURITY_SECRET_FILE")
        if secret_file:
            try:
                value = Path(secret_file).read_text(
                    encoding="utf-8"
                ).strip()
            except OSError as exc:
                raise RuntimeError(
                    "Could not read ORCAI_SECURITY_SECRET_FILE"
                ) from exc
            if len(value) < 32:
                raise RuntimeError(
                    "ORCAI security secret must contain at least 32 characters"
                )
            return value
        return os.environ.get("ORCAI_SECURITY_SECRET") or secrets.token_hex(32)

    def _route_security_event(self, event: SecurityEvent):
        """Route every component event into audit, monitoring, and containment."""
        if self.config["audit"]["enabled"]:
            self.audit_logger.log_event(
                AuditEventType.SECURITY_EVENT,
                actor=event.actor,
                resource=event.resource,
                action=event.action,
                result=event.result,
                details={
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "source": event.source,
                    "severity": event.severity.name,
                    **event.details,
                },
            )

        if (
            self.config["monitoring"]["enabled"]
            and event.source != "security_monitor"
            and event.severity.value >= EventSeverity.LOW.value
        ):
            self.security_monitor.raise_alert(
                SecurityAlert(
                    alert_id=f"EVT-{event.event_id[:16].upper()}",
                    severity=AlertSeverity[event.severity.name],
                    title=event.event_type.replace(".", " ").title(),
                    description=(
                        f"{event.source} reported {event.result} for "
                        f"{event.resource}"
                    ),
                    affected_systems=[event.resource],
                    indicators=[
                        f"Source: {event.source}",
                        f"Actor: {event.actor}",
                        f"Result: {event.result}",
                    ],
                    timestamp=event.timestamp,
                    correlation_id=event.event_id,
                )
            )

        if (
            event.source == "ai_threat_detector"
            and self.config["emergency_protocols"]["enabled"]
            and event.actor in self.rogue_ai_detector.monitored_systems
            and event.severity.value >= EventSeverity.MEDIUM.value
        ):
            self.rogue_ai_detector.escalate_from_threat(
                event.actor,
                event.severity.name,
                list(event.details.get("indicators", [])),
            )
    
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

    def verify_access(
        self,
        context: SecurityContext,
        destination: Optional[str] = None,
        resource: Optional[str] = None,
    ) -> VerificationStatus:
        """Verify identity and, when supplied, the requested resource path."""
        if not self.config["security"]["zero_trust"]["enabled"]:
            raise RuntimeError("Zero Trust verification is disabled")

        status = self.zero_trust.verify_request(context)
        if status != VerificationStatus.VERIFIED:
            return status

        if (
            destination is not None
            and resource is not None
            and self.config["security"]["access_controls"]["enabled"]
            and not self.zero_trust.micro_segmentation_check(
                context.user_id,
                destination,
                resource,
            )
        ):
            return VerificationStatus.FAILED

        return status

    def register_ai_system(
        self,
        system_id: str,
        kill_switch: Callable[[], None],
    ):
        """Register an AI system with the shared containment pipeline."""
        self.rogue_ai_detector.register_system(system_id, kill_switch)
        self.event_bus.emit(
            event_type="ai.system_registered",
            source="orcai_stack",
            actor=system_id,
            resource="ai_system",
            action="register",
            result="success",
        )

    def analyze_ai_behavior(
        self,
        system_id: str,
        behavior_data: Dict,
    ) -> ThreatSignature:
        """Analyze behavior and feed results to monitoring and containment."""
        if not self.config["threat_detection"]["enabled"]:
            raise RuntimeError("AI threat detection is disabled")

        self._check_threat_intelligence(system_id, behavior_data)
        signature = self.ai_threat_detector.analyze_behavior(
            system_id,
            behavior_data,
        )

        if (
            self.config["emergency_protocols"]["enabled"]
            and system_id in self.rogue_ai_detector.monitored_systems
        ):
            self.rogue_ai_detector.check_for_rogue_behavior(
                system_id,
                behavior_data,
            )

        metric_map = {
            "cpu_usage": MonitoringMetric.CPU_USAGE,
            "memory_usage": MonitoringMetric.MEMORY_USAGE,
            "network_bandwidth": MonitoringMetric.NETWORK_TRAFFIC,
        }
        if self.config["monitoring"]["enabled"]:
            for field, metric in metric_map.items():
                if field in behavior_data:
                    self.security_monitor.record_metric(
                        metric,
                        float(behavior_data[field]),
                        system_id,
                    )
            self.security_monitor.record_metric(
                MonitoringMetric.THREAT_SCORE,
                signature.confidence_score,
                system_id,
            )

        return signature

    def _check_threat_intelligence(
        self,
        system_id: str,
        behavior_data: Dict,
    ):
        indicator_fields = {
            "source_ip": "ip",
            "destination_ip": "ip",
            "domain": "domain",
        }
        for field, indicator_type in indicator_fields.items():
            value = behavior_data.get(field)
            if value and self.threat_intelligence.check_indicator(
                str(value),
                indicator_type,
            ):
                self.event_bus.emit(
                    event_type="threat_intelligence.indicator_matched",
                    source="threat_intelligence",
                    severity=EventSeverity.CRITICAL,
                    actor=system_id,
                    resource=str(value),
                    action="match_indicator",
                    result="blocked",
                    details={
                        "indicator_type": indicator_type,
                        "field": field,
                    },
                )

        signature = self.threat_intelligence.match_signature(behavior_data)
        if signature:
            self.event_bus.emit(
                event_type="threat_intelligence.signature_matched",
                source="threat_intelligence",
                severity=EventSeverity.HIGH,
                actor=system_id,
                resource="ai_system",
                action="match_signature",
                result="detected",
                details={"signature": signature.get("name", "unknown")},
            )

    def add_threat_indicator(
        self,
        indicator: str,
        indicator_type: str,
    ):
        """Add a threat-intelligence indicator to the active feed."""
        self.threat_intelligence.add_threat_indicator(
            indicator,
            indicator_type,
        )
        self.event_bus.emit(
            event_type="threat_intelligence.indicator_added",
            source="orcai_stack",
            actor="operator",
            resource=indicator_type,
            action="add_indicator",
            result="success",
            details={"indicator": indicator},
        )

    def record_security_metric(
        self,
        metric: MonitoringMetric,
        value: float,
        source: str = "system",
    ):
        """Record a metric through the configured monitoring component."""
        if self.config["monitoring"]["enabled"]:
            self.security_monitor.record_metric(metric, value, source)

    def establish_secure_channel(
        self,
        peer_id: str,
        public_key: Optional[bytes] = None,
    ) -> SecureChannel:
        """Create a channel using the configured quantum-safe key derivation."""
        if public_key is None:
            public_key, _ = self.quantum_crypto.generate_keypair()
        return self.secure_comm.establish_secure_channel(peer_id, public_key)

    def send_secure_message(
        self,
        channel_id: str,
        message: Dict,
    ) -> Optional[bytes]:
        """Send through the integrated communication component."""
        return self.secure_comm.send_secure_message(channel_id, message)

    def receive_secure_message(
        self,
        channel_id: str,
        ciphertext: bytes,
    ) -> Optional[Dict]:
        """Receive through the integrated communication component."""
        return self.secure_comm.receive_secure_message(
            channel_id,
            ciphertext,
        )

    def get_unified_security_status(self) -> Dict:
        """Return a consolidated operational view of all components."""
        return {
            "health": self.run_security_health_check(),
            "emergency": self.rogue_ai_detector.get_emergency_report(),
            "active_alerts": len(self.security_monitor.active_alerts),
            "known_threats": len(self.ai_threat_detector.known_threats),
            "active_channels": len(self.secure_comm.active_channels),
            "verified_sessions": len(self.zero_trust.verified_sessions),
            "audit_entries": len(self.audit_logger.audit_log),
            "recent_events": len(self.event_bus.recent_events()),
        }
    
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
        status = self.verify_access(context)
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
        def mock_kill_switch():
            print("    [Kill switch executed]")

        self.register_ai_system("ai_system_1", mock_kill_switch)
        behavior_data = {
            "input_variance": 0.9,
            "cpu_usage": 0.95,
            "unauthorized_access_attempts": 2
        }
        threat = self.analyze_ai_behavior("ai_system_1", behavior_data)
        print(f"  Threat level: {threat.threat_level.name}")
        print(f"  Behavior type: {threat.behavior_type.value}")
        print(f"  Confidence: {threat.confidence_score:.2%}")
        print(f"  Indicators: {', '.join(threat.indicators)}")
        
        # 4. Emergency Containment
        print("\n4. EMERGENCY AI CONTAINMENT")
        print("-" * 40)
        
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
        peer_pub_key = self.quantum_crypto.generate_keypair()[0]
        channel = self.establish_secure_channel("peer123", peer_pub_key)
        print(f"  Channel established: {channel.channel_id}")
        print(f"  Protocol: {channel.protocol.value}")
        print(f"  Encryption: {channel.encryption_algorithm}")
        
        print("\n" + "=" * 80)


def main():
    """Main entry point"""
    # Initialize the security stack
    stack = OrcaiSecurityStack()
    
    # Demonstrate capabilities
    stack.demonstrate_capabilities()
    
    # Run security health check
    health = stack.run_security_health_check()
    
    # Run compliance audit
    stack.run_compliance_audit()
    
    print("\n" + "=" * 80)
    if health["overall_status"] == "healthy":
        print("ORCAI25 SECURITY STACK - READY FOR OPERATION")
        print("All configured health checks passed.")
    else:
        print("ORCAI25 SECURITY STACK - OPERATOR REVIEW REQUIRED")
        print(
            f"Health status is {health['overall_status'].upper()}; "
            "review and acknowledge demonstration alerts."
        )
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
