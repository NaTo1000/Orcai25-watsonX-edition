"""
Zero Trust Architecture Framework
Implements "never trust, always verify" security model for enterprise systems
"""

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set
import secrets


class TrustLevel(Enum):
    """Trust levels for zero trust verification"""
    UNTRUSTED = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class VerificationStatus(Enum):
    """Status of verification checks"""
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    SUSPICIOUS = "suspicious"


@dataclass
class SecurityContext:
    """Security context for request verification"""
    user_id: str
    device_id: str
    ip_address: str
    timestamp: float
    session_token: str
    trust_level: TrustLevel
    mfa_verified: bool
    behavioral_score: float


class ZeroTrustEngine:
    """
    Core Zero Trust Architecture engine
    Continuously verifies every access request regardless of location
    """
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode()
        self.verified_sessions: Dict[str, SecurityContext] = {}
        self.blocked_entities: Set[str] = set()
        self.suspicious_activities: List[Dict] = []
        
    def verify_request(self, context: SecurityContext) -> VerificationStatus:
        """
        Verify every request against zero trust principles
        No implicit trust based on network location
        """
        # Check if entity is blocked
        if context.user_id in self.blocked_entities:
            self._log_security_event("BLOCKED_ENTITY_ATTEMPTED_ACCESS", context)
            return VerificationStatus.FAILED
        
        # Verify session token
        if not self._verify_token(context.session_token, context.user_id):
            self._log_security_event("INVALID_TOKEN", context)
            return VerificationStatus.FAILED
        
        # Check timestamp for replay attacks
        current_time = time.time()
        if abs(current_time - context.timestamp) > 300:  # 5 minute window
            self._log_security_event("TIMESTAMP_ANOMALY", context)
            return VerificationStatus.SUSPICIOUS
        
        # Verify MFA for high trust operations
        if context.trust_level.value >= TrustLevel.HIGH.value and not context.mfa_verified:
            self._log_security_event("MFA_REQUIRED", context)
            return VerificationStatus.FAILED
        
        # Check behavioral analysis score
        if context.behavioral_score < 0.3:
            self._log_security_event("LOW_BEHAVIORAL_SCORE", context)
            return VerificationStatus.SUSPICIOUS
        
        # Store verified session
        self.verified_sessions[context.session_token] = context
        return VerificationStatus.VERIFIED
    
    def _verify_token(self, token: str, user_id: str) -> bool:
        """Verify session token using HMAC"""
        try:
            token_parts = token.split('.')
            if len(token_parts) != 2:
                return False
            
            payload, signature = token_parts
            expected_signature = hmac.new(
                self.secret_key,
                f"{payload}:{user_id}".encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
        except Exception:
            return False
    
    def generate_secure_token(self, user_id: str) -> str:
        """Generate cryptographically secure session token"""
        payload = secrets.token_urlsafe(32)
        signature = hmac.new(
            self.secret_key,
            f"{payload}:{user_id}".encode(),
            hashlib.sha256
        ).hexdigest()
        return f"{payload}.{signature}"
    
    def _log_security_event(self, event_type: str, context: SecurityContext):
        """Log security events for audit and monitoring"""
        event = {
            "event_type": event_type,
            "user_id": context.user_id,
            "device_id": context.device_id,
            "ip_address": context.ip_address,
            "timestamp": time.time(),
            "trust_level": context.trust_level.name
        }
        self.suspicious_activities.append(event)
        print(f"[SECURITY EVENT] {event_type}: {json.dumps(event)}")
    
    def micro_segmentation_check(self, source: str, destination: str, 
                                 resource: str) -> bool:
        """
        Implement micro-segmentation for resource access
        Each resource requires explicit authorization
        """
        # Principle of least privilege - deny by default
        allowed_paths = self._get_allowed_paths(source)
        
        resource_path = f"{destination}/{resource}"
        if resource_path not in allowed_paths:
            self._log_security_event(
                "UNAUTHORIZED_RESOURCE_ACCESS",
                SecurityContext(
                    user_id=source,
                    device_id="unknown",
                    ip_address="unknown",
                    timestamp=time.time(),
                    session_token="",
                    trust_level=TrustLevel.UNTRUSTED,
                    mfa_verified=False,
                    behavioral_score=0.0
                )
            )
            return False
        
        return True
    
    def _get_allowed_paths(self, entity: str) -> Set[str]:
        """Get allowed resource paths for entity (placeholder for policy engine)"""
        # In production, this would query a policy engine
        return set()
    
    def continuous_verification(self, session_token: str) -> bool:
        """
        Continuously verify active sessions
        Trust is never permanent in zero trust model
        """
        if session_token not in self.verified_sessions:
            return False
        
        context = self.verified_sessions[session_token]
        
        # Re-verify periodically
        if time.time() - context.timestamp > 3600:  # 1 hour re-verification
            del self.verified_sessions[session_token]
            return False
        
        return True
    
    def block_entity(self, entity_id: str, reason: str):
        """Block suspicious entity from all access"""
        self.blocked_entities.add(entity_id)
        print(f"[SECURITY] Blocked entity {entity_id}: {reason}")
        
        # Remove all sessions for blocked entity
        sessions_to_remove = [
            token for token, ctx in self.verified_sessions.items()
            if ctx.user_id == entity_id
        ]
        for token in sessions_to_remove:
            del self.verified_sessions[token]
