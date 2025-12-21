"""
Real-Time Security Monitoring and Alerting System
Provides continuous monitoring, anomaly detection, and security event correlation
"""

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Callable
from collections import defaultdict
import statistics


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class MonitoringMetric(Enum):
    """Types of metrics to monitor"""
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    NETWORK_TRAFFIC = "network_traffic"
    FAILED_LOGINS = "failed_logins"
    API_ERRORS = "api_errors"
    UNUSUAL_ACTIVITY = "unusual_activity"
    THREAT_SCORE = "threat_score"


@dataclass
class SecurityAlert:
    """Security alert data structure"""
    alert_id: str
    severity: AlertSeverity
    title: str
    description: str
    affected_systems: List[str]
    indicators: List[str]
    timestamp: float
    correlation_id: Optional[str] = None


class SecurityMonitor:
    """
    Real-time security monitoring system
    Detects anomalies and correlates security events
    """
    
    def __init__(self):
        self.metrics_history: Dict[MonitoringMetric, List[float]] = defaultdict(list)
        self.active_alerts: List[SecurityAlert] = []
        self.alert_handlers: Dict[AlertSeverity, List[Callable]] = defaultdict(list)
        self.baseline_established = False
        self.baselines: Dict[MonitoringMetric, Dict] = {}
        self.event_correlations: Dict[str, List[str]] = defaultdict(list)
        
    def record_metric(self, metric: MonitoringMetric, value: float, 
                     source: str = "system"):
        """Record security metric and check for anomalies"""
        self.metrics_history[metric].append(value)
        
        # Keep last 1000 values
        if len(self.metrics_history[metric]) > 1000:
            self.metrics_history[metric] = self.metrics_history[metric][-1000:]
        
        # Establish baseline if enough data
        if len(self.metrics_history[metric]) >= 100 and not self.baseline_established:
            self._establish_baseline(metric)
        
        # Check for anomalies
        if self.baseline_established:
            anomaly = self._detect_anomaly(metric, value)
            if anomaly:
                self._trigger_anomaly_alert(metric, value, source, anomaly)
    
    def _establish_baseline(self, metric: MonitoringMetric):
        """Establish baseline for normal behavior"""
        values = self.metrics_history[metric]
        
        self.baselines[metric] = {
            "mean": statistics.mean(values),
            "stddev": statistics.stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values),
            "percentile_95": self._percentile(values, 0.95)
        }
        
        print(f"[MONITORING] Baseline established for {metric.value}: {self.baselines[metric]}")
    
    def _percentile(self, values: List[float], p: float) -> float:
        """Calculate percentile"""
        sorted_values = sorted(values)
        index = int(len(sorted_values) * p)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def _detect_anomaly(self, metric: MonitoringMetric, value: float) -> Optional[Dict]:
        """Detect if value is anomalous compared to baseline"""
        if metric not in self.baselines:
            return None
        
        baseline = self.baselines[metric]
        mean = baseline["mean"]
        stddev = baseline["stddev"]
        
        # Z-score anomaly detection
        if stddev > 0:
            z_score = abs((value - mean) / stddev)
            
            if z_score > 3:  # 3 standard deviations
                return {
                    "type": "statistical_anomaly",
                    "z_score": z_score,
                    "threshold": 3,
                    "value": value,
                    "expected_range": [mean - 3*stddev, mean + 3*stddev]
                }
        
        # Percentile-based detection
        if value > baseline["percentile_95"] * 1.5:
            return {
                "type": "percentile_anomaly",
                "value": value,
                "threshold": baseline["percentile_95"] * 1.5
            }
        
        return None
    
    def _trigger_anomaly_alert(self, metric: MonitoringMetric, value: float,
                              source: str, anomaly: Dict):
        """Trigger alert for detected anomaly"""
        # Determine severity based on deviation
        if "z_score" in anomaly:
            if anomaly["z_score"] > 5:
                severity = AlertSeverity.CRITICAL
            elif anomaly["z_score"] > 4:
                severity = AlertSeverity.HIGH
            else:
                severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.MEDIUM
        
        alert = SecurityAlert(
            alert_id=f"ANOM-{int(time.time() * 1000)}",
            severity=severity,
            title=f"Anomaly Detected: {metric.value}",
            description=f"Unusual {metric.value} detected from {source}",
            affected_systems=[source],
            indicators=[
                f"Metric: {metric.value}",
                f"Value: {value}",
                f"Anomaly type: {anomaly.get('type', 'unknown')}"
            ],
            timestamp=time.time()
        )
        
        self.raise_alert(alert)
    
    def raise_alert(self, alert: SecurityAlert):
        """Raise security alert and trigger handlers"""
        self.active_alerts.append(alert)
        
        # Log alert
        alert_data = {
            "alert_id": alert.alert_id,
            "severity": alert.severity.name,
            "title": alert.title,
            "description": alert.description,
            "affected_systems": alert.affected_systems,
            "indicators": alert.indicators,
            "timestamp": alert.timestamp
        }
        print(f"[SECURITY ALERT] {json.dumps(alert_data)}")
        
        # Trigger alert handlers
        for handler in self.alert_handlers.get(alert.severity, []):
            try:
                handler(alert)
            except Exception as e:
                print(f"[ALERT HANDLER ERROR] {e}")
        
        # Correlate with other events
        self._correlate_events(alert)
    
    def _correlate_events(self, alert: SecurityAlert):
        """
        Correlate security events to identify attack patterns
        """
        # Check for related alerts in last 5 minutes
        recent_time = time.time() - 300
        related_alerts = [
            a for a in self.active_alerts
            if a.timestamp > recent_time and a.alert_id != alert.alert_id
        ]
        
        # Look for correlation patterns
        if len(related_alerts) >= 3:
            # Multiple alerts suggest coordinated attack
            correlation_id = f"CORR-{int(time.time())}"
            
            correlated_alert = SecurityAlert(
                alert_id=f"CORR-{int(time.time() * 1000)}",
                severity=AlertSeverity.CRITICAL,
                title="Correlated Attack Pattern Detected",
                description=f"Multiple security events detected: possible coordinated attack",
                affected_systems=list(set(
                    sys for a in related_alerts + [alert]
                    for sys in a.affected_systems
                )),
                indicators=[
                    f"Correlated events: {len(related_alerts) + 1}",
                    f"Time window: 5 minutes",
                    "Pattern: Multiple security violations"
                ],
                timestamp=time.time(),
                correlation_id=correlation_id
            )
            
            print(f"[EVENT CORRELATION] {correlation_id}: {len(related_alerts) + 1} events")
            self.active_alerts.append(correlated_alert)
    
    def register_alert_handler(self, severity: AlertSeverity, 
                              handler: Callable[[SecurityAlert], None]):
        """Register handler for specific alert severity"""
        self.alert_handlers[severity].append(handler)
        print(f"[MONITORING] Registered alert handler for {severity.name}")
    
    def get_active_alerts(self, min_severity: AlertSeverity = AlertSeverity.LOW) -> List[SecurityAlert]:
        """Get active alerts above minimum severity"""
        return [
            alert for alert in self.active_alerts
            if alert.severity.value >= min_severity.value
        ]
    
    def acknowledge_alert(self, alert_id: str):
        """Acknowledge and clear alert"""
        self.active_alerts = [
            alert for alert in self.active_alerts
            if alert.alert_id != alert_id
        ]
        print(f"[MONITORING] Alert acknowledged: {alert_id}")
    
    def get_metrics_summary(self) -> Dict:
        """Get summary of current metrics"""
        summary = {}
        
        for metric, values in self.metrics_history.items():
            if values:
                summary[metric.value] = {
                    "current": values[-1],
                    "average": statistics.mean(values[-100:]) if len(values) >= 100 else statistics.mean(values),
                    "max": max(values[-100:]) if len(values) >= 100 else max(values),
                    "samples": len(values)
                }
        
        return summary
    
    def run_health_check(self, system_config: Dict) -> Dict:
        """
        Comprehensive security health check
        """
        health_status = {
            "timestamp": time.time(),
            "overall_status": "healthy",
            "checks": {}
        }
        
        # Check encryption
        health_status["checks"]["encryption"] = {
            "status": "pass" if system_config.get("encryption_enabled") else "fail",
            "critical": True
        }
        
        # Check access controls
        health_status["checks"]["access_controls"] = {
            "status": "pass" if system_config.get("access_controls_enabled") else "fail",
            "critical": True
        }
        
        # Check audit logging
        health_status["checks"]["audit_logging"] = {
            "status": "pass" if system_config.get("audit_logging_enabled") else "fail",
            "critical": True
        }
        
        # Check intrusion detection
        health_status["checks"]["intrusion_detection"] = {
            "status": "pass" if system_config.get("intrusion_detection_enabled") else "fail",
            "critical": False
        }
        
        # Check for active critical alerts
        critical_alerts = len([a for a in self.active_alerts 
                              if a.severity == AlertSeverity.CRITICAL])
        health_status["checks"]["active_critical_alerts"] = {
            "status": "pass" if critical_alerts == 0 else "fail",
            "critical": True,
            "count": critical_alerts
        }
        
        # Determine overall status
        critical_failures = sum(
            1 for check in health_status["checks"].values()
            if check.get("critical") and check["status"] == "fail"
        )
        
        if critical_failures > 0:
            health_status["overall_status"] = "critical"
        elif any(check["status"] == "fail" for check in health_status["checks"].values()):
            health_status["overall_status"] = "degraded"
        
        print(f"[HEALTH CHECK] Overall status: {health_status['overall_status']}")
        
        return health_status


class ThreatIntelligenceFeed:
    """
    Threat intelligence integration
    Provides real-time threat indicators and patterns
    """
    
    def __init__(self):
        self.threat_indicators: Set[str] = set()
        self.malicious_ips: Set[str] = set()
        self.malicious_domains: Set[str] = set()
        self.attack_signatures: List[Dict] = []
        
    def add_threat_indicator(self, indicator: str, indicator_type: str):
        """Add threat indicator from intelligence feed"""
        self.threat_indicators.add(indicator)
        
        if indicator_type == "ip":
            self.malicious_ips.add(indicator)
        elif indicator_type == "domain":
            self.malicious_domains.add(indicator)
        
        print(f"[THREAT INTEL] Added indicator: {indicator_type}={indicator}")
    
    def check_indicator(self, value: str, indicator_type: str) -> bool:
        """Check if value matches known threat indicator"""
        if indicator_type == "ip":
            return value in self.malicious_ips
        elif indicator_type == "domain":
            return value in self.malicious_domains
        
        return value in self.threat_indicators
    
    def add_attack_signature(self, signature: Dict):
        """Add attack signature for detection"""
        self.attack_signatures.append(signature)
        print(f"[THREAT INTEL] Added attack signature: {signature.get('name', 'unknown')}")
    
    def match_signature(self, event_data: Dict) -> Optional[Dict]:
        """Check if event matches known attack signature"""
        for signature in self.attack_signatures:
            if self._signature_matches(signature, event_data):
                return signature
        return None
    
    def _signature_matches(self, signature: Dict, event_data: Dict) -> bool:
        """Check if event matches signature pattern"""
        # Simple pattern matching (in production, use more sophisticated matching)
        required_fields = signature.get("required_fields", [])
        
        for field in required_fields:
            if field not in event_data:
                return False
        
        return True
