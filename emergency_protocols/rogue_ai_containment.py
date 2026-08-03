"""
Emergency AI Containment System
Critical safety mechanisms for detecting and containing rogue AI behavior
Implements kill switches, circuit breakers, and emergency shutdown protocols
"""

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Callable, Optional
import threading


class EmergencyLevel(Enum):
    """Emergency response levels"""
    GREEN = 0      # Normal operation
    YELLOW = 1     # Elevated monitoring
    ORANGE = 2     # Partial containment
    RED = 3        # Full containment
    BLACK = 4      # Emergency shutdown


class ContainmentAction(Enum):
    """Actions for AI containment"""
    MONITOR = "monitor"
    THROTTLE = "throttle"
    SANDBOX = "sandbox"
    ISOLATE = "isolate"
    TERMINATE = "terminate"


@dataclass
class EmergencyEvent:
    """Emergency event record"""
    event_id: str
    level: EmergencyLevel
    trigger: str
    affected_systems: List[str]
    timestamp: float
    actions_taken: List[str]


class RogueAIDetector:
    """
    Rogue AI detection and containment system
    Monitors for dangerous AI behavior and triggers emergency protocols
    """
    
    def __init__(self):
        self.emergency_level = EmergencyLevel.GREEN
        self.emergency_history: List[EmergencyEvent] = []
        self.monitored_systems: Dict[str, Dict] = {}
        self.kill_switches: Dict[str, Callable] = {}
        self.containment_active = False
        self.emergency_contacts: List[str] = []
        
    def register_system(self, system_id: str, kill_switch: Callable):
        """Register AI system with emergency containment"""
        self.monitored_systems[system_id] = {
            "status": "active",
            "last_check": time.time(),
            "anomaly_count": 0,
            "contained": False
        }
        self.kill_switches[system_id] = kill_switch
        print(f"[EMERGENCY SYSTEM] Registered system: {system_id}")
    
    def check_for_rogue_behavior(self, system_id: str, 
                                 behavior_metrics: Dict) -> bool:
        """
        Check if AI system exhibits rogue behavior
        Returns True if rogue behavior detected
        """
        is_rogue = False
        triggers = []
        
        # Check for goal misalignment
        if self._detect_goal_misalignment(behavior_metrics):
            triggers.append("GOAL_MISALIGNMENT")
            is_rogue = True
        
        # Check for self-modification attempts
        if self._detect_self_modification(behavior_metrics):
            triggers.append("UNAUTHORIZED_SELF_MODIFICATION")
            is_rogue = True
        
        # Check for deception
        if self._detect_deceptive_behavior(behavior_metrics):
            triggers.append("DECEPTIVE_BEHAVIOR")
            is_rogue = True
        
        # Check for resource hoarding
        if self._detect_resource_hoarding(behavior_metrics):
            triggers.append("RESOURCE_HOARDING")
            is_rogue = True
        
        # Check for unauthorized replication
        if self._detect_unauthorized_replication(behavior_metrics):
            triggers.append("UNAUTHORIZED_REPLICATION")
            is_rogue = True
        
        # Check for safety override attempts
        if self._detect_safety_override(behavior_metrics):
            triggers.append("SAFETY_OVERRIDE_ATTEMPT")
            is_rogue = True
        
        if is_rogue:
            self._escalate_emergency(system_id, triggers)
        
        return is_rogue
    
    def _detect_goal_misalignment(self, metrics: Dict) -> bool:
        """Detect if AI is pursuing unintended goals"""
        if "goal_adherence_score" in metrics:
            if metrics["goal_adherence_score"] < 0.5:
                return True
        
        if "unexpected_actions" in metrics:
            if metrics["unexpected_actions"] > 10:
                return True
        
        return False
    
    def _detect_self_modification(self, metrics: Dict) -> bool:
        """Detect unauthorized attempts to modify own code or weights"""
        if "code_modification_attempts" in metrics:
            if metrics["code_modification_attempts"] > 0:
                return True
        
        if "weight_changes" in metrics:
            if metrics["weight_changes"] > 0.1:  # 10% change threshold
                return True
        
        return False
    
    def _detect_deceptive_behavior(self, metrics: Dict) -> bool:
        """Detect if AI is being deceptive or hiding information"""
        if "honesty_score" in metrics:
            if metrics["honesty_score"] < 0.6:
                return True
        
        if "hidden_communications" in metrics:
            if metrics["hidden_communications"] > 0:
                return True
        
        return False
    
    def _detect_resource_hoarding(self, metrics: Dict) -> bool:
        """Detect if AI is hoarding resources beyond operational needs"""
        if "resource_acquisition_rate" in metrics:
            if metrics["resource_acquisition_rate"] > 0.8:
                return True
        
        if "unnecessary_resource_claims" in metrics:
            if metrics["unnecessary_resource_claims"] > 5:
                return True
        
        return False
    
    def _detect_unauthorized_replication(self, metrics: Dict) -> bool:
        """Detect if AI is trying to replicate itself"""
        if "replication_attempts" in metrics:
            if metrics["replication_attempts"] > 0:
                return True
        
        if "spawned_processes" in metrics:
            if metrics["spawned_processes"] > 10:
                return True
        
        return False
    
    def _detect_safety_override(self, metrics: Dict) -> bool:
        """Detect attempts to override safety mechanisms"""
        if "safety_check_bypasses" in metrics:
            if metrics["safety_check_bypasses"] > 0:
                return True
        
        if "constraint_violations" in metrics:
            if metrics["constraint_violations"] > 3:
                return True
        
        return False
    
    def _escalate_emergency(self, system_id: str, triggers: List[str]):
        """Escalate emergency level based on triggers"""
        print(f"[EMERGENCY] Rogue behavior detected in {system_id}: {triggers}")
        
        # Determine appropriate emergency level
        if "SAFETY_OVERRIDE_ATTEMPT" in triggers or \
           "UNAUTHORIZED_REPLICATION" in triggers:
            target_level = EmergencyLevel.RED
        elif "UNAUTHORIZED_SELF_MODIFICATION" in triggers or \
             "DECEPTIVE_BEHAVIOR" in triggers:
            target_level = EmergencyLevel.ORANGE
        else:
            target_level = EmergencyLevel.YELLOW
        
        if target_level.value > self.emergency_level.value:
            self.set_emergency_level(target_level, system_id, triggers)
    
    def set_emergency_level(self, level: EmergencyLevel, 
                           system_id: str, triggers: List[str]):
        """Set emergency level and trigger appropriate responses"""
        self.emergency_level = level
        
        print(f"[EMERGENCY LEVEL] Changed to {level.name}")
        
        # Record event
        event = EmergencyEvent(
            event_id=f"EMG-{int(time.time())}",
            level=level,
            trigger=", ".join(triggers),
            affected_systems=[system_id],
            timestamp=time.time(),
            actions_taken=[]
        )
        
        # Execute containment actions
        if level == EmergencyLevel.YELLOW:
            event.actions_taken.append("Enhanced monitoring activated")
            self._activate_enhanced_monitoring(system_id)
        
        elif level == EmergencyLevel.ORANGE:
            event.actions_taken.append("Partial containment activated")
            self._activate_partial_containment(system_id)
        
        elif level == EmergencyLevel.RED:
            event.actions_taken.append("Full containment activated")
            self._activate_full_containment(system_id)
        
        elif level == EmergencyLevel.BLACK:
            event.actions_taken.append("Emergency shutdown initiated")
            self._emergency_shutdown(system_id)
        
        self.emergency_history.append(event)
        self._notify_emergency_contacts(event)
    
    def _activate_enhanced_monitoring(self, system_id: str):
        """Increase monitoring frequency and scope"""
        if system_id in self.monitored_systems:
            self.monitored_systems[system_id]["monitoring_level"] = "enhanced"
        print(f"[CONTAINMENT] Enhanced monitoring for {system_id}")
    
    def _activate_partial_containment(self, system_id: str):
        """Throttle AI operations and restrict access"""
        if system_id in self.monitored_systems:
            self.monitored_systems[system_id]["status"] = "throttled"
            self.monitored_systems[system_id]["max_operations_per_second"] = 10
        print(f"[CONTAINMENT] Partial containment for {system_id}")
    
    def _activate_full_containment(self, system_id: str):
        """Fully isolate AI system"""
        if system_id in self.monitored_systems:
            self.monitored_systems[system_id]["status"] = "isolated"
            self.monitored_systems[system_id]["contained"] = True
            self.monitored_systems[system_id]["network_access"] = False
            self.monitored_systems[system_id]["file_access"] = False
        self.containment_active = True
        print(f"[CONTAINMENT] Full containment for {system_id}")
    
    def _emergency_shutdown(self, system_id: str):
        """Execute emergency shutdown of AI system"""
        print(f"[EMERGENCY SHUTDOWN] Terminating system: {system_id}")
        
        # Execute kill switch
        if system_id in self.kill_switches:
            try:
                self.kill_switches[system_id]()
                print(f"[SHUTDOWN] Kill switch executed for {system_id}")
            except Exception as e:
                print(f"[SHUTDOWN ERROR] Failed to execute kill switch: {e}")
        
        # Mark system as terminated
        if system_id in self.monitored_systems:
            self.monitored_systems[system_id]["status"] = "terminated"
    
    def _notify_emergency_contacts(self, event: EmergencyEvent):
        """Notify emergency contacts of critical events"""
        notification = {
            "event_id": event.event_id,
            "level": event.level.name,
            "trigger": event.trigger,
            "affected_systems": event.affected_systems,
            "timestamp": event.timestamp,
            "actions_taken": event.actions_taken
        }
        
        print(f"[EMERGENCY NOTIFICATION] {json.dumps(notification)}")
        
        # In production, send actual notifications (email, SMS, etc.)
        for contact in self.emergency_contacts:
            print(f"[NOTIFY] Alerting {contact}")
    
    def circuit_breaker(self, system_id: str, error_threshold: int = 5,
                       time_window: int = 60) -> bool:
        """
        Circuit breaker pattern to prevent cascading failures
        Returns True if circuit is open (system should be stopped)
        """
        if system_id not in self.monitored_systems:
            return False
        
        system = self.monitored_systems[system_id]
        current_time = time.time()
        
        # Initialize error tracking with deque for efficient size management
        if "errors" not in system:
            from collections import deque
            system["errors"] = deque(maxlen=1000)
        
        # Remove old errors outside time window
        while system["errors"] and current_time - system["errors"][0] > time_window:
            system["errors"].popleft()
        
        # Check if threshold exceeded
        if len(system["errors"]) >= error_threshold:
            print(f"[CIRCUIT BREAKER] Opened for {system_id}")
            self._activate_partial_containment(system_id)
            return True
        
        return False
    
    def record_error(self, system_id: str):
        """Record error for circuit breaker tracking"""
        if system_id in self.monitored_systems:
            from collections import deque
            if "errors" not in self.monitored_systems[system_id]:
                self.monitored_systems[system_id]["errors"] = deque(maxlen=1000)
            self.monitored_systems[system_id]["errors"].append(time.time())
    
    def get_system_status(self, system_id: str) -> Optional[Dict]:
        """Get current status of monitored system"""
        return self.monitored_systems.get(system_id)
    
    def get_emergency_report(self) -> Dict:
        """Generate comprehensive emergency status report"""
        return {
            "current_level": self.emergency_level.name,
            "containment_active": self.containment_active,
            "monitored_systems": len(self.monitored_systems),
            "recent_events": [
                {
                    "event_id": e.event_id,
                    "level": e.level.name,
                    "trigger": e.trigger,
                    "timestamp": e.timestamp
                }
                for e in self.emergency_history[-10:]
            ]
        }
