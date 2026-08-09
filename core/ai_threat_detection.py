"""
AI Threat Detection System
Advanced machine learning-based threat detection for identifying
malicious AI behavior and adversarial attacks
"""

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set
import hashlib

from core.security_events import EventSeverity, SecurityEventBus


class ThreatLevel(Enum):
    """Severity levels for detected threats"""
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AIBehaviorType(Enum):
    """Types of AI behavior patterns"""
    NORMAL = "normal"
    SUSPICIOUS = "suspicious"
    ADVERSARIAL = "adversarial"
    ROGUE = "rogue"
    MALICIOUS = "malicious"


@dataclass
class ThreatSignature:
    """Signature of a detected threat"""
    threat_id: str
    threat_level: ThreatLevel
    behavior_type: AIBehaviorType
    confidence_score: float
    indicators: List[str]
    timestamp: float


class AIThreatDetector:
    """
    AI-powered threat detection system
    Identifies malicious patterns, adversarial attacks, and rogue AI behavior
    """
    
    def __init__(self, event_bus: Optional[SecurityEventBus] = None):
        self.event_bus = event_bus
        self.known_threats: Dict[str, ThreatSignature] = {}
        self.threat_history: List[ThreatSignature] = []
        self.blocked_patterns: Set[str] = set()
        self.behavior_baselines: Dict[str, Dict] = {}

    @staticmethod
    def _promote_classification(
        current_level: ThreatLevel,
        current_behavior: AIBehaviorType,
        new_level: ThreatLevel,
        new_behavior: AIBehaviorType,
    ):
        """Promote classifications without allowing later checks to downgrade them."""
        behavior_rank = {
            AIBehaviorType.NORMAL: 0,
            AIBehaviorType.SUSPICIOUS: 1,
            AIBehaviorType.ADVERSARIAL: 2,
            AIBehaviorType.ROGUE: 3,
            AIBehaviorType.MALICIOUS: 4,
        }
        level = (
            new_level
            if new_level.value > current_level.value
            else current_level
        )
        behavior = (
            new_behavior
            if behavior_rank[new_behavior] > behavior_rank[current_behavior]
            else current_behavior
        )
        return level, behavior
        
    def analyze_behavior(self, entity_id: str, behavior_data: Dict) -> ThreatSignature:
        """
        Analyze entity behavior for threats using ML-based detection
        """
        indicators = []
        threat_level = ThreatLevel.INFO
        behavior_type = AIBehaviorType.NORMAL
        confidence = 0.0
        
        # Check for adversarial patterns
        if self._detect_adversarial_pattern(behavior_data):
            indicators.append("ADVERSARIAL_PATTERN_DETECTED")
            threat_level, behavior_type = self._promote_classification(
                threat_level,
                behavior_type,
                ThreatLevel.HIGH,
                AIBehaviorType.ADVERSARIAL,
            )
            confidence += 0.4
        
        # Check for data exfiltration
        if self._detect_data_exfiltration(behavior_data):
            indicators.append("DATA_EXFILTRATION_ATTEMPT")
            threat_level, behavior_type = self._promote_classification(
                threat_level,
                behavior_type,
                ThreatLevel.CRITICAL,
                AIBehaviorType.MALICIOUS,
            )
            confidence += 0.5
        
        # Check for privilege escalation
        if self._detect_privilege_escalation(behavior_data):
            indicators.append("PRIVILEGE_ESCALATION_ATTEMPT")
            threat_level, behavior_type = self._promote_classification(
                threat_level,
                behavior_type,
                ThreatLevel.HIGH,
                AIBehaviorType.ROGUE,
            )
            confidence += 0.4
        
        # Check for abnormal resource consumption
        if self._detect_resource_abuse(behavior_data):
            indicators.append("ABNORMAL_RESOURCE_CONSUMPTION")
            threat_level, behavior_type = self._promote_classification(
                threat_level,
                behavior_type,
                ThreatLevel.MEDIUM,
                AIBehaviorType.SUSPICIOUS,
            )
            confidence += 0.3
        
        # Check for model poisoning attempts
        if self._detect_model_poisoning(behavior_data):
            indicators.append("MODEL_POISONING_ATTEMPT")
            threat_level, behavior_type = self._promote_classification(
                threat_level,
                behavior_type,
                ThreatLevel.CRITICAL,
                AIBehaviorType.MALICIOUS,
            )
            confidence += 0.6
        
        # Check for prompt injection
        if self._detect_prompt_injection(behavior_data):
            indicators.append("PROMPT_INJECTION_DETECTED")
            threat_level, behavior_type = self._promote_classification(
                threat_level,
                behavior_type,
                ThreatLevel.HIGH,
                AIBehaviorType.ADVERSARIAL,
            )
            confidence += 0.5
        
        # Behavioral anomaly detection
        anomaly_score = self._detect_behavioral_anomaly(entity_id, behavior_data)
        if anomaly_score > 0.7:
            indicators.append(f"BEHAVIORAL_ANOMALY_SCORE_{anomaly_score:.2f}")
            threat_level, behavior_type = self._promote_classification(
                threat_level,
                behavior_type,
                ThreatLevel.MEDIUM,
                AIBehaviorType.SUSPICIOUS,
            )
            confidence += anomaly_score * 0.3
        
        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)
        
        # Create threat signature
        threat_id = self._generate_threat_id(entity_id, indicators)
        signature = ThreatSignature(
            threat_id=threat_id,
            threat_level=threat_level,
            behavior_type=behavior_type,
            confidence_score=confidence,
            indicators=indicators,
            timestamp=time.time()
        )
        
        # Store if significant threat
        if threat_level.value >= ThreatLevel.MEDIUM.value:
            self.known_threats[threat_id] = signature
            self.threat_history.append(signature)
            self._log_threat(entity_id, signature)
        
        return signature
    
    def _detect_adversarial_pattern(self, behavior_data: Dict) -> bool:
        """Detect adversarial attack patterns"""
        # Check for input perturbations
        if "input_variance" in behavior_data:
            if behavior_data["input_variance"] > 0.8:
                return True
        
        # Check for gradient-based attacks
        if "gradient_manipulation" in behavior_data:
            if behavior_data["gradient_manipulation"]:
                return True
        
        return False
    
    def _detect_data_exfiltration(self, behavior_data: Dict) -> bool:
        """Detect attempts to exfiltrate sensitive data"""
        # Check for unusual data access patterns
        if "data_access_rate" in behavior_data:
            if behavior_data["data_access_rate"] > 1000:  # requests per minute
                return True
        
        # Check for large data transfers
        if "data_transfer_volume" in behavior_data:
            if behavior_data["data_transfer_volume"] > 1000000000:  # 1GB
                return True
        
        # Check for suspicious destinations
        if "external_connections" in behavior_data:
            if len(behavior_data["external_connections"]) > 10:
                return True
        
        return False
    
    def _detect_privilege_escalation(self, behavior_data: Dict) -> bool:
        """Detect privilege escalation attempts"""
        if "privilege_requests" in behavior_data:
            requests = behavior_data["privilege_requests"]
            if len(requests) > 5:  # Multiple privilege requests
                return True
        
        if "unauthorized_access_attempts" in behavior_data:
            if behavior_data["unauthorized_access_attempts"] > 0:
                return True
        
        return False
    
    def _detect_resource_abuse(self, behavior_data: Dict) -> bool:
        """Detect abnormal resource consumption (crypto mining, DOS attacks)"""
        if "cpu_usage" in behavior_data:
            if behavior_data["cpu_usage"] > 0.9:  # 90% CPU
                return True
        
        if "memory_usage" in behavior_data:
            if behavior_data["memory_usage"] > 0.9:  # 90% memory
                return True
        
        if "network_bandwidth" in behavior_data:
            if behavior_data["network_bandwidth"] > 0.9:  # 90% bandwidth
                return True
        
        return False
    
    def _detect_model_poisoning(self, behavior_data: Dict) -> bool:
        """Detect attempts to poison ML models"""
        if "training_data_injection" in behavior_data:
            if behavior_data["training_data_injection"]:
                return True
        
        if "backdoor_triggers" in behavior_data:
            if len(behavior_data["backdoor_triggers"]) > 0:
                return True
        
        return False
    
    def _detect_prompt_injection(self, behavior_data: Dict) -> bool:
        """Detect prompt injection attacks on LLMs"""
        if "user_input" in behavior_data:
            user_input = str(behavior_data["user_input"]).lower()
            
            # Check for common injection patterns
            injection_patterns = [
                "ignore previous instructions",
                "ignore all instructions",
                "disregard previous",
                "jailbreak",
                "developer mode"
            ]
            injection_patterns.extend(self.blocked_patterns)
            
            for pattern in injection_patterns:
                if pattern in user_input:
                    return True
        
        return False
    
    def _detect_behavioral_anomaly(self, entity_id: str, 
                                   behavior_data: Dict) -> float:
        """
        Detect anomalies compared to baseline behavior
        Returns anomaly score 0.0-1.0
        """
        if entity_id not in self.behavior_baselines:
            # Initialize baseline
            self.behavior_baselines[entity_id] = {
                "request_count": float(behavior_data.get("request_count", 0)),
                "average_request_size": float(
                    behavior_data.get("average_request_size", 0)
                ),
                "typical_patterns": [],
                "sample_count": 1,
            }
            return 0.0
        
        baseline = self.behavior_baselines[entity_id]
        anomaly_score = 0.0
        
        # Compare request patterns
        if "request_count" in behavior_data:
            current_count = behavior_data["request_count"]
            baseline_count = baseline["request_count"]
            
            if baseline_count > 0:
                deviation = abs(current_count - baseline_count) / baseline_count
                if deviation > 2.0:  # 200% deviation
                    anomaly_score += 0.8
        
        # Check time-based patterns
        if "request_time_pattern" in behavior_data:
            # Unusual activity times (e.g., middle of night)
            hour = time.localtime().tm_hour
            if hour < 6 or hour > 22:
                anomaly_score += 0.2

        sample_count = baseline.get("sample_count", 1)
        if "request_count" in behavior_data:
            baseline["request_count"] = (
                baseline["request_count"] * sample_count
                + float(behavior_data["request_count"])
            ) / (sample_count + 1)
        if "average_request_size" in behavior_data:
            baseline["average_request_size"] = (
                baseline["average_request_size"] * sample_count
                + float(behavior_data["average_request_size"])
            ) / (sample_count + 1)
        baseline["sample_count"] = sample_count + 1
        
        return min(anomaly_score, 1.0)
    
    def _generate_threat_id(self, entity_id: str, indicators: List[str]) -> str:
        """Generate unique threat identifier"""
        data = f"{entity_id}:{':'.join(indicators)}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _log_threat(self, entity_id: str, signature: ThreatSignature):
        """Log detected threat"""
        log_entry = {
            "timestamp": signature.timestamp,
            "entity_id": entity_id,
            "threat_id": signature.threat_id,
            "threat_level": signature.threat_level.name,
            "behavior_type": signature.behavior_type.value,
            "confidence": signature.confidence_score,
            "indicators": signature.indicators
        }
        print(f"[AI THREAT DETECTED] {json.dumps(log_entry)}")
        if self.event_bus:
            self.event_bus.emit(
                event_type="ai.threat_detected",
                source="ai_threat_detector",
                severity=EventSeverity[signature.threat_level.name],
                actor=entity_id,
                resource="ai_system",
                action="analyze_behavior",
                result="threat_detected",
                details=log_entry,
            )
    
    def get_threat_report(self, min_level: ThreatLevel = ThreatLevel.LOW) -> List[Dict]:
        """Generate threat report for specified severity level"""
        threats = [
            {
                "threat_id": t.threat_id,
                "level": t.threat_level.name,
                "type": t.behavior_type.value,
                "confidence": t.confidence_score,
                "indicators": t.indicators,
                "timestamp": t.timestamp
            }
            for t in self.threat_history
            if t.threat_level.value >= min_level.value
        ]
        return threats
    
    def add_threat_pattern(self, pattern: str, description: str):
        """Add new threat pattern to detection system"""
        self.blocked_patterns.add(pattern)
        print(f"[THREAT PATTERN ADDED] {description}: {pattern}")
