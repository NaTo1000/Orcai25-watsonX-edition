"""Shared security event pipeline used by the Orcai25 components."""

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import threading
import time
from typing import Any, Callable, Deque, Dict, List, Optional
import uuid


class EventSeverity(Enum):
    """Normalized severity levels for cross-component events."""

    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class SecurityEvent:
    """A normalized event that can be audited, monitored, and persisted."""

    event_id: str
    event_type: str
    source: str
    severity: EventSeverity
    actor: str
    resource: str
    action: str
    result: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


EventHandler = Callable[[SecurityEvent], None]


class SecurityEventBus:
    """Thread-safe synchronous event dispatcher with bounded history."""

    def __init__(self, history_size: int = 1000):
        if history_size < 1:
            raise ValueError("history_size must be positive")
        self._history: Deque[SecurityEvent] = deque(maxlen=history_size)
        self._handlers: List[EventHandler] = []
        self._lock = threading.RLock()

    def subscribe(self, handler: EventHandler) -> None:
        """Register an event handler once."""
        with self._lock:
            if handler not in self._handlers:
                self._handlers.append(handler)

    def unsubscribe(self, handler: EventHandler) -> None:
        """Remove a previously registered event handler."""
        with self._lock:
            if handler in self._handlers:
                self._handlers.remove(handler)

    def emit(
        self,
        event_type: str,
        source: str,
        severity: EventSeverity = EventSeverity.INFO,
        actor: str = "system",
        resource: str = "orcai_security_stack",
        action: str = "observe",
        result: str = "recorded",
        details: Optional[Dict[str, Any]] = None,
    ) -> SecurityEvent:
        """Create and publish an event."""
        event = SecurityEvent(
            event_id=uuid.uuid4().hex,
            event_type=event_type,
            source=source,
            severity=severity,
            actor=actor,
            resource=resource,
            action=action,
            result=result,
            details=dict(details or {}),
        )
        self.publish(event)
        return event

    def publish(self, event: SecurityEvent) -> None:
        """Publish an existing event without allowing one handler to stop others."""
        with self._lock:
            self._history.append(event)
            handlers = tuple(self._handlers)

        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                print(f"[EVENT HANDLER ERROR] {handler!r}: {exc}")

    def recent_events(
        self,
        limit: int = 100,
        min_severity: EventSeverity = EventSeverity.INFO,
    ) -> List[SecurityEvent]:
        """Return recent events ordered from oldest to newest."""
        if limit < 1:
            return []
        with self._lock:
            matching = [
                event
                for event in self._history
                if event.severity.value >= min_severity.value
            ]
        return matching[-limit:]
