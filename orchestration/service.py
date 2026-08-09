"""Application service coordinating security, models, skills, and jobs."""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import sqlite3
from typing import Dict, Iterable, List, Optional

from core.ai_threat_detection import ThreatLevel
from core.security_events import EventSeverity, SecurityEvent
from core.zero_trust_architecture import (
    SecurityContext,
    TrustLevel,
    VerificationStatus,
)
from orcai_security import OrcaiSecurityStack
from orchestration.benchmarks import BenchmarkManager
from orchestration.database import OrchestrationDatabase
from orchestration.huggingface import (
    HuggingFaceCatalog,
    validate_repo_id,
)
from orchestration.quantum import QuantumProviderManager
from orchestration.runners import ModelRunnerManager


SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
SKILL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{1,63}$")
SAFE_SKILL_PROMPT_LIMIT = 12000


class OrchestrationService:
    """Tenant-aware facade for every VPS orchestration operation."""

    def __init__(
        self,
        database_path: Optional[str] = None,
        runtime_directory: Optional[str] = None,
        security_config_path: str = "config/security_config.json",
        huggingface_owner: Optional[str] = None,
    ):
        root = Path(__file__).resolve().parent.parent
        data_path = database_path or os.environ.get(
            "ORCAI_DATABASE_PATH",
            str(root / "data" / "orchestration.db"),
        )
        runtime_path = runtime_directory or os.environ.get(
            "ORCAI_RUNTIME_DIRECTORY",
            str(root / "data" / "runtime"),
        )
        self.database = OrchestrationDatabase(data_path)
        self.database.reconcile_interrupted_work()
        self.stack = OrcaiSecurityStack(security_config_path)
        self._tenant_context: ContextVar[Optional[str]] = ContextVar(
            "orcai_tenant_id",
            default=None,
        )
        self.stack.event_bus.subscribe(self._persist_security_event)

        self.catalog = HuggingFaceCatalog(
            owner=huggingface_owner
            or os.environ.get("ORCAI_HUGGINGFACE_OWNER", "NaTo10000")
        )
        self.runners = ModelRunnerManager(
            self.database,
            str(Path(runtime_path) / "runners"),
            max_concurrent_runs=int(
                os.environ.get("ORCAI_MAX_MODEL_RUNNERS", "2")
            ),
        )
        self.benchmarks = BenchmarkManager(
            self.database,
            str(Path(runtime_path) / "benchmarks"),
            event_callback=self._benchmark_event,
        )
        self.quantum = QuantumProviderManager(
            self.database,
            event_callback=self._quantum_event,
        )

    @contextmanager
    def tenant_scope(self, tenant_id: str):
        token = self._tenant_context.set(tenant_id)
        try:
            yield
        finally:
            self._tenant_context.reset(token)

    def _persist_security_event(self, event: SecurityEvent):
        tenant_id = (
            event.details.get("tenant_id")
            or self._tenant_context.get()
        )
        self.database.record_security_event(
            tenant_id,
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "source": event.source,
                "severity": event.severity.name,
                "actor": event.actor,
                "resource": event.resource,
                "action": event.action,
                "result": event.result,
                "details": event.details,
                "created_at": datetime.fromtimestamp(
                    event.timestamp,
                    timezone.utc,
                ).isoformat(),
            },
        )

    def _emit_tenant_event(
        self,
        tenant_id: str,
        event_type: str,
        actor: str,
        resource: str,
        action: str,
        result: str,
        severity: EventSeverity = EventSeverity.INFO,
        details: Optional[Dict] = None,
    ):
        self.stack.event_bus.emit(
            event_type=event_type,
            source="orchestration_service",
            severity=severity,
            actor=actor,
            resource=resource,
            action=action,
            result=result,
            details={"tenant_id": tenant_id, **(details or {})},
        )

    def bootstrap(
        self,
        tenant_name: str,
        tenant_slug: str = "naydoev1",
    ) -> Dict:
        tenant_name = tenant_name.strip()
        tenant_slug = tenant_slug.strip().lower()
        if not 2 <= len(tenant_name) <= 120:
            raise ValueError("Tenant name must be between 2 and 120 characters")
        if not SLUG_PATTERN.fullmatch(tenant_slug):
            raise ValueError("Invalid tenant slug")
        if self.database.get_tenant_by_slug(tenant_slug):
            raise ValueError("Tenant slug already exists")

        tenant = self.database.create_tenant(tenant_name, tenant_slug)
        with self.tenant_scope(tenant["id"]):
            identity = self.register_naydoev1(tenant["id"])
            key = self.database.create_api_key(
                tenant["id"],
                "bootstrap-admin",
                {"admin", "benchmark", "control", "quantum", "read", "skills"},
            )
            self._emit_tenant_event(
                tenant["id"],
                "saas.tenant_bootstrapped",
                key["id"],
                tenant_slug,
                "bootstrap",
                "success",
                details={"model_id": identity["id"]},
            )
        return {"tenant": tenant, "identity": identity, "api_key": key}

    def create_api_key(
        self,
        tenant_id: str,
        name: str,
        scopes: Iterable[str],
    ) -> Dict:
        allowed = {"admin", "benchmark", "control", "quantum", "read", "skills"}
        normalized = set(scopes)
        if not normalized or not normalized.issubset(allowed):
            raise ValueError("API key contains invalid scopes")
        return self.database.create_api_key(
            tenant_id,
            name.strip()[:120],
            normalized,
        )

    def register_naydoev1(self, tenant_id: str) -> Dict:
        repo_id = "NaTo10000/NayDoeV1"
        existing = self.database.get_model_by_repo(tenant_id, repo_id)
        if existing:
            return existing

        date = datetime.now(timezone.utc).strftime("%Y%m%d")
        entropy = hashlib.sha256(
            f"{tenant_id}:{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:12].upper()
        return self.database.register_model(
            tenant_id=tenant_id,
            name="NayDoeV1",
            owner="NaTo10000",
            source_repo=repo_id,
            source_verified=False,
            model_number="NDV1-ORCH-V1",
            serial_number=f"NDV1-{date}-{entropy}",
            role_title="Conductor of Orchestrated Symphonies",
            registry_scope="Orcai25 tenant registry",
            metadata={
                "identity_status": "registered",
                "identity_issuer": "Orcai25 orchestration service",
                "external_registry_status": "unverified",
                "benchmark_status": "not_yet_measured",
                "claim_boundary": (
                    "This identity is genuine within the tenant registry; "
                    "it is not a claim of government, legal, IBM, or "
                    "Hugging Face certification."
                ),
            },
        )

    def public_naydoev1_profile(
        self,
        tenant_slug: Optional[str] = None,
    ) -> Optional[Dict]:
        slug = tenant_slug or os.environ.get(
            "ORCAI_PUBLIC_TENANT_SLUG",
            "naydoev1",
        )
        tenant = self.database.get_tenant_by_slug(slug)
        if not tenant:
            return None
        model = self.database.get_model_by_repo(
            tenant["id"],
            "NaTo10000/NayDoeV1",
        )
        if not model:
            return None
        return {
            "name": model["name"],
            "owner": model["owner"],
            "model_number": model["model_number"],
            "serial_number": model["serial_number"],
            "role_title": model["role_title"],
            "registry_scope": model["registry_scope"],
            "registration_hash": model["registration_hash"],
            "source_repo": model["source_repo"],
            "source_verified": model["source_verified"],
            "metadata": model["metadata"],
            "registered_at": model["created_at"],
        }

    def refresh_huggingface(self, tenant_id: str) -> List[Dict]:
        with self.tenant_scope(tenant_id):
            discovered = self.catalog.discover()
            for item in discovered:
                existing = self.database.get_model_by_repo(
                    tenant_id,
                    item["repo_id"],
                )
                if existing:
                    metadata = {**existing["metadata"], **item}
                    metadata["external_registry_status"] = "verified_public"
                    self.database.update_model_verification(
                        tenant_id,
                        item["repo_id"],
                        True,
                        metadata,
                    )
                    continue

                digest = hashlib.sha256(
                    f"{tenant_id}:{item['repo_id']}".encode()
                ).hexdigest().upper()
                self.database.register_model(
                    tenant_id=tenant_id,
                    name=item["name"],
                    owner=item["owner"],
                    source_repo=item["repo_id"],
                    source_verified=True,
                    model_number=f"HF-{digest[:12]}",
                    serial_number=f"HF-{digest[12:32]}",
                    role_title=None,
                    registry_scope="Hugging Face public catalog",
                    metadata={
                        **item,
                        "external_registry_status": "verified_public",
                    },
                )
            self._emit_tenant_event(
                tenant_id,
                "models.huggingface_refreshed",
                "operator",
                self.catalog.owner,
                "refresh",
                "success",
                details={"models_discovered": len(discovered)},
            )
            return self.database.list_models(tenant_id)

    def model_commands(
        self,
        tenant_id: str,
        model_id: str,
        port: int = 8001,
    ) -> Dict[str, str]:
        model = self.database.get_model(tenant_id, model_id)
        if not model:
            raise KeyError("Model not found")
        return self.catalog.commands(model["source_repo"], port)

    def create_skill(
        self,
        tenant_id: str,
        name: str,
        description: str,
        system_prompt: str,
        allowed_models: List[str],
    ) -> Dict:
        name = name.strip()
        description = description.strip()
        system_prompt = system_prompt.strip()
        if not SKILL_NAME_PATTERN.fullmatch(name):
            raise ValueError("Invalid skill name")
        if not 1 <= len(description) <= 500:
            raise ValueError("Skill description must be 1 to 500 characters")
        if not 1 <= len(system_prompt) <= SAFE_SKILL_PROMPT_LIMIT:
            raise ValueError("Skill prompt is empty or too large")

        model_ids = {
            model["id"] for model in self.database.list_models(tenant_id)
        }
        if not allowed_models or not set(allowed_models).issubset(model_ids):
            raise ValueError("Skill references an unknown model")

        with self.tenant_scope(tenant_id):
            threat = self.stack.ai_threat_detector.analyze_behavior(
                f"skill:{name}",
                {"user_input": system_prompt},
            )
            if threat.threat_level.value >= ThreatLevel.HIGH.value:
                raise ValueError(
                    "Skill prompt was rejected by prompt-injection controls"
                )
            try:
                skill = self.database.create_skill(
                    tenant_id,
                    name,
                    description,
                    system_prompt,
                    allowed_models,
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("Skill name already exists") from exc
            self._emit_tenant_event(
                tenant_id,
                "skills.created",
                "operator",
                skill["id"],
                "create_skill",
                "success",
            )
            return skill

    def delete_skill(self, tenant_id: str, skill_id: str):
        if not self.database.delete_skill(tenant_id, skill_id):
            raise KeyError("Skill not found")
        self._emit_tenant_event(
            tenant_id,
            "skills.deleted",
            "operator",
            skill_id,
            "delete_skill",
            "success",
        )

    def start_model(
        self,
        tenant_id: str,
        model_id: str,
        runner: str,
        port: int,
    ) -> Dict:
        model = self.database.get_model(tenant_id, model_id)
        if not model:
            raise KeyError("Model not found")
        with self.tenant_scope(tenant_id):
            run = self.runners.start(
                tenant_id,
                model,
                runner,
                port,
            )
            self._emit_tenant_event(
                tenant_id,
                "models.runner_started",
                "operator",
                run["id"],
                "start_runner",
                "success",
                EventSeverity.MEDIUM,
                {"model_id": model_id, "runner": runner, "port": port},
            )
            return run

    def stop_model(self, tenant_id: str, run_id: str) -> Dict:
        with self.tenant_scope(tenant_id):
            run = self.runners.stop(tenant_id, run_id)
            self._emit_tenant_event(
                tenant_id,
                "models.runner_stopped",
                "operator",
                run_id,
                "stop_runner",
                "success",
                EventSeverity.MEDIUM,
            )
            return run

    def start_benchmark(
        self,
        tenant_id: str,
        model_id: str,
        tasks: List[str],
        limit: Optional[int] = None,
    ) -> Dict:
        model = self.database.get_model(tenant_id, model_id)
        if not model:
            raise KeyError("Model not found")
        with self.tenant_scope(tenant_id):
            return self.benchmarks.start(
                tenant_id,
                model,
                tasks,
                limit,
            )

    def _benchmark_event(self, benchmark_id: str, status: str, details: Dict):
        tenant_id = details.pop("tenant_id", None)
        if tenant_id:
            self._emit_tenant_event(
                tenant_id,
                f"benchmark.{status}",
                "benchmark_runner",
                benchmark_id,
                "run_benchmark",
                status,
                EventSeverity.INFO
                if status in {"queued", "running", "completed"}
                else EventSeverity.HIGH,
                details,
            )

    def submit_quantum_job(
        self,
        tenant_id: str,
        provider: str,
        backend_mode: str,
        target: Optional[str],
        circuit: Dict,
        shots: int,
        confirm_hardware: bool,
    ) -> Dict:
        with self.tenant_scope(tenant_id):
            return self.quantum.submit(
                tenant_id,
                provider,
                backend_mode,
                target,
                circuit,
                shots,
                confirm_hardware,
            )

    def _quantum_event(self, job_id: str, status: str, details: Dict):
        tenant_id = details.pop("tenant_id", None)
        if tenant_id:
            self._emit_tenant_event(
                tenant_id,
                f"quantum.{status}",
                "quantum_engine",
                job_id,
                "quantum_job",
                status,
                EventSeverity.INFO
                if status in {"queued", "submitted", "completed"}
                else EventSeverity.HIGH,
                details,
            )

    def authorize_request(
        self,
        principal: Dict,
        ip_address: str,
        path: str,
    ):
        tenant_id = principal["tenant_id"]
        with self.tenant_scope(tenant_id):
            token = self.stack.zero_trust.generate_secure_token(
                principal["key_id"]
            )
            context = SecurityContext(
                user_id=principal["key_id"],
                device_id="api-key",
                ip_address=ip_address,
                timestamp=datetime.now(timezone.utc).timestamp(),
                session_token=token,
                trust_level=TrustLevel.MEDIUM,
                mfa_verified=False,
                behavioral_score=1.0,
            )
            try:
                status = self.stack.verify_access(context)
            finally:
                self.stack.zero_trust.verified_sessions.pop(token, None)
            if status != VerificationStatus.VERIFIED:
                raise PermissionError(f"Zero Trust status: {status.value}")
            self._emit_tenant_event(
                tenant_id,
                "saas.api_request",
                principal["key_id"],
                path,
                "authorize",
                "verified",
            )

    def status(self, tenant_id: str) -> Dict:
        return {
            "tenant": self.database.get_tenant(tenant_id),
            "models": len(self.database.list_models(tenant_id)),
            "skills": len(self.database.list_skills(tenant_id)),
            "runners": self.runners.available_runners(),
            "quantum_providers": self.quantum.provider_status(),
            "security": {
                "emergency_level": self.stack.rogue_ai_detector.emergency_level.name,
                "active_alerts": len(self.stack.security_monitor.active_alerts),
                "audit_integrity": self.stack.audit_logger.verify_integrity(),
            },
        }
