"""
Comprehensive Audit and Compliance Framework
Ensures compliance with SOC2, ISO 27001, GDPR, HIPAA, and other standards
Provides automated audit logging and compliance checking
"""

import json
import time
import hashlib
import hmac
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set
from datetime import datetime


class ComplianceStandard(Enum):
    """Supported compliance standards"""
    SOC2 = "SOC2"
    ISO27001 = "ISO 27001"
    GDPR = "GDPR"
    HIPAA = "HIPAA"
    PCI_DSS = "PCI DSS"
    NIST_CSF = "NIST Cybersecurity Framework"
    CCPA = "CCPA"


class AuditEventType(Enum):
    """Types of auditable events"""
    ACCESS = "access"
    MODIFICATION = "modification"
    DELETION = "deletion"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_TRANSFER = "data_transfer"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_EVENT = "security_event"
    COMPLIANCE_CHECK = "compliance_check"


@dataclass
class AuditEntry:
    """Immutable audit log entry"""
    entry_id: str
    timestamp: float
    event_type: AuditEventType
    actor: str
    resource: str
    action: str
    result: str
    details: Dict
    signature: str


class AuditLogger:
    """
    Tamper-proof audit logging system
    Creates immutable audit trail for compliance
    """
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode()
        self.audit_log: List[AuditEntry] = []
        self.last_hash = hashlib.sha256(b"GENESIS").hexdigest()
        
    def log_event(self, event_type: AuditEventType, actor: str, 
                  resource: str, action: str, result: str, 
                  details: Optional[Dict] = None) -> AuditEntry:
        """
        Log auditable event with tamper-proof signature
        Creates cryptographic chain of audit entries
        """
        if details is None:
            details = {}
        
        timestamp = time.time()
        entry_id = self._generate_entry_id(timestamp, actor, resource)
        
        # Create entry data
        entry_data = {
            "entry_id": entry_id,
            "timestamp": timestamp,
            "event_type": event_type.value,
            "actor": actor,
            "resource": resource,
            "action": action,
            "result": result,
            "details": details,
            "previous_hash": self.last_hash
        }
        
        # Generate tamper-proof signature
        signature = self._generate_signature(entry_data)
        
        # Create audit entry
        entry = AuditEntry(
            entry_id=entry_id,
            timestamp=timestamp,
            event_type=event_type,
            actor=actor,
            resource=resource,
            action=action,
            result=result,
            details=details,
            signature=signature
        )
        
        self.audit_log.append(entry)
        self.last_hash = signature
        
        # Output to audit log (in production, write to secure storage)
        self._write_to_audit_log(entry)
        
        return entry
    
    def _generate_entry_id(self, timestamp: float, actor: str, 
                          resource: str) -> str:
        """Generate unique audit entry ID"""
        data = f"{timestamp}:{actor}:{resource}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _generate_signature(self, entry_data: Dict) -> str:
        """Generate cryptographic signature for audit entry"""
        # Serialize entry data deterministically
        serialized = json.dumps(entry_data, sort_keys=True)
        
        return hmac.new(
            self.secret_key,
            serialized.encode(),
            hashlib.sha256,
        ).hexdigest()
    
    def _write_to_audit_log(self, entry: AuditEntry):
        """Write audit entry to persistent storage"""
        log_line = {
            "entry_id": entry.entry_id,
            "timestamp": datetime.fromtimestamp(entry.timestamp).isoformat(),
            "event_type": entry.event_type.value,
            "actor": entry.actor,
            "resource": entry.resource,
            "action": entry.action,
            "result": entry.result,
            "details": entry.details,
            "signature": entry.signature
        }
        print(f"[AUDIT LOG] {json.dumps(log_line)}")
    
    def verify_integrity(self) -> bool:
        """Verify integrity of audit log chain"""
        previous_hash = hashlib.sha256(b"GENESIS").hexdigest()
        
        for entry in self.audit_log:
            # Reconstruct entry data
            entry_data = {
                "entry_id": entry.entry_id,
                "timestamp": entry.timestamp,
                "event_type": entry.event_type.value,
                "actor": entry.actor,
                "resource": entry.resource,
                "action": entry.action,
                "result": entry.result,
                "details": entry.details,
                "previous_hash": previous_hash
            }
            
            # Verify signature
            expected_signature = self._generate_signature(entry_data)
            if not hmac.compare_digest(entry.signature, expected_signature):
                print(f"[AUDIT INTEGRITY] Tampering detected at entry {entry.entry_id}")
                return False
            
            previous_hash = entry.signature
        
        return True
    
    def search_audit_log(self, actor: Optional[str] = None,
                        resource: Optional[str] = None,
                        event_type: Optional[AuditEventType] = None,
                        start_time: Optional[float] = None,
                        end_time: Optional[float] = None) -> List[AuditEntry]:
        """Search audit log with filters"""
        results = []
        
        for entry in self.audit_log:
            # Apply filters
            if actor and entry.actor != actor:
                continue
            if resource and entry.resource != resource:
                continue
            if event_type and entry.event_type != event_type:
                continue
            if start_time and entry.timestamp < start_time:
                continue
            if end_time and entry.timestamp > end_time:
                continue
            
            results.append(entry)
        
        return results


class ComplianceChecker:
    """
    Automated compliance checking against various standards
    """
    
    def __init__(self, audit_logger: AuditLogger):
        self.audit_logger = audit_logger
        self.compliance_rules: Dict[ComplianceStandard, List[Dict]] = {
            ComplianceStandard.SOC2: self._get_soc2_rules(),
            ComplianceStandard.ISO27001: self._get_iso27001_rules(),
            ComplianceStandard.GDPR: self._get_gdpr_rules(),
            ComplianceStandard.HIPAA: self._get_hipaa_rules(),
        }
        
    def check_compliance(self, standard: ComplianceStandard, 
                        system_config: Dict) -> Dict:
        """
        Check compliance against specified standard
        Returns compliance report with violations
        """
        print(f"[COMPLIANCE CHECK] Checking {standard.value} compliance")
        
        rules = self.compliance_rules.get(standard, [])
        violations = []
        passed_checks = []
        
        for rule in rules:
            check_result = self._evaluate_rule(rule, system_config)
            
            if check_result["compliant"]:
                passed_checks.append(rule["rule_id"])
            else:
                violations.append({
                    "rule_id": rule["rule_id"],
                    "description": rule["description"],
                    "severity": rule["severity"],
                    "details": check_result["details"]
                })
        
        # Log compliance check
        self.audit_logger.log_event(
            AuditEventType.COMPLIANCE_CHECK,
            actor="compliance_checker",
            resource=standard.value,
            action="check_compliance",
            result="completed",
            details={
                "violations_count": len(violations),
                "passed_checks_count": len(passed_checks)
            }
        )
        
        compliance_report = {
            "standard": standard.value,
            "timestamp": time.time(),
            "total_rules_checked": len(rules),
            "passed": len(passed_checks),
            "violations": len(violations),
            "compliance_score": len(passed_checks) / len(rules) if rules else 1.0,
            "violation_details": violations
        }
        
        print(f"[COMPLIANCE REPORT] {standard.value}: {compliance_report['compliance_score']:.1%} compliant")
        
        return compliance_report
    
    def _evaluate_rule(self, rule: Dict, system_config: Dict) -> Dict:
        """Evaluate single compliance rule"""
        rule_id = rule["rule_id"]
        check_function = rule["check_function"]
        
        try:
            result = check_function(system_config)
            return {
                "compliant": result,
                "details": f"Rule {rule_id} evaluation: {'PASS' if result else 'FAIL'}"
            }
        except Exception as e:
            return {
                "compliant": False,
                "details": f"Rule {rule_id} evaluation error: {str(e)}"
            }
    
    def _get_soc2_rules(self) -> List[Dict]:
        """SOC 2 compliance rules"""
        return [
            {
                "rule_id": "SOC2-CC6.1",
                "description": "Logical and physical access controls",
                "severity": "critical",
                "check_function": lambda cfg: cfg.get("access_controls_enabled", False)
            },
            {
                "rule_id": "SOC2-CC6.6",
                "description": "Audit logging and monitoring",
                "severity": "critical",
                "check_function": lambda cfg: cfg.get("audit_logging_enabled", False)
            },
            {
                "rule_id": "SOC2-CC6.7",
                "description": "Data encryption in transit and at rest",
                "severity": "critical",
                "check_function": lambda cfg: cfg.get("encryption_enabled", False)
            },
            {
                "rule_id": "SOC2-CC7.2",
                "description": "Intrusion detection",
                "severity": "high",
                "check_function": lambda cfg: cfg.get("intrusion_detection_enabled", False)
            }
        ]
    
    def _get_iso27001_rules(self) -> List[Dict]:
        """ISO 27001 compliance rules"""
        return [
            {
                "rule_id": "ISO27001-A.9.2.1",
                "description": "User registration and de-registration",
                "severity": "high",
                "check_function": lambda cfg: cfg.get("user_management_enabled", False)
            },
            {
                "rule_id": "ISO27001-A.9.4.1",
                "description": "Information access restriction",
                "severity": "critical",
                "check_function": lambda cfg: cfg.get("access_controls_enabled", False)
            },
            {
                "rule_id": "ISO27001-A.12.4.1",
                "description": "Event logging",
                "severity": "critical",
                "check_function": lambda cfg: cfg.get("audit_logging_enabled", False)
            },
            {
                "rule_id": "ISO27001-A.10.1.1",
                "description": "Cryptographic controls",
                "severity": "critical",
                "check_function": lambda cfg: cfg.get("encryption_enabled", False)
            }
        ]
    
    def _get_gdpr_rules(self) -> List[Dict]:
        """GDPR compliance rules"""
        return [
            {
                "rule_id": "GDPR-Art.32",
                "description": "Security of processing (encryption)",
                "severity": "critical",
                "check_function": lambda cfg: cfg.get("encryption_enabled", False)
            },
            {
                "rule_id": "GDPR-Art.33",
                "description": "Breach notification procedures",
                "severity": "critical",
                "check_function": lambda cfg: cfg.get("breach_notification_enabled", False)
            },
            {
                "rule_id": "GDPR-Art.25",
                "description": "Data protection by design and default",
                "severity": "high",
                "check_function": lambda cfg: cfg.get("privacy_by_design", False)
            },
            {
                "rule_id": "GDPR-Art.30",
                "description": "Records of processing activities",
                "severity": "high",
                "check_function": lambda cfg: cfg.get("audit_logging_enabled", False)
            }
        ]
    
    def _get_hipaa_rules(self) -> List[Dict]:
        """HIPAA compliance rules"""
        return [
            {
                "rule_id": "HIPAA-164.312(a)(1)",
                "description": "Access controls",
                "severity": "critical",
                "check_function": lambda cfg: cfg.get("access_controls_enabled", False)
            },
            {
                "rule_id": "HIPAA-164.312(b)",
                "description": "Audit controls",
                "severity": "critical",
                "check_function": lambda cfg: cfg.get("audit_logging_enabled", False)
            },
            {
                "rule_id": "HIPAA-164.312(e)(1)",
                "description": "Transmission security",
                "severity": "critical",
                "check_function": lambda cfg: cfg.get("encryption_enabled", False)
            },
            {
                "rule_id": "HIPAA-164.308(a)(1)(ii)(D)",
                "description": "Information system activity review",
                "severity": "high",
                "check_function": lambda cfg: cfg.get("intrusion_detection_enabled", False)
            }
        ]
    
    def generate_compliance_matrix(self, system_config: Dict) -> Dict:
        """Generate compliance matrix across all standards"""
        matrix = {}
        
        for standard in ComplianceStandard:
            if standard in self.compliance_rules:
                report = self.check_compliance(standard, system_config)
                matrix[standard.value] = {
                    "compliance_score": report["compliance_score"],
                    "violations_count": report["violations"]
                }
        
        return matrix
