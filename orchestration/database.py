"""SQLite persistence for the Orcai25 orchestration service."""

import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3
import threading
from typing import Any, Dict, Iterable, List, Optional
import uuid


API_KEY_PATTERN = re.compile(
    r"^orc_live_([0-9a-f]{16})_([A-Za-z0-9_-]{32,})$"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrchestrationDatabase:
    """Small multi-tenant data layer with no stored plaintext API keys."""

    def __init__(self, path: str):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._schema_lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=10,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self):
        with self._schema_lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    name TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    secret_hash TEXT NOT NULL,
                    scopes_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    revoked_at TEXT
                );

                CREATE TABLE IF NOT EXISTS models (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    name TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    source_repo TEXT,
                    source_verified INTEGER NOT NULL DEFAULT 0,
                    model_number TEXT NOT NULL,
                    serial_number TEXT NOT NULL UNIQUE,
                    role_title TEXT,
                    registry_scope TEXT NOT NULL,
                    registration_hash TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id, source_repo)
                );

                CREATE TABLE IF NOT EXISTS skills (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    system_prompt TEXT NOT NULL,
                    allowed_models_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id, name)
                );

                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    model_id TEXT NOT NULL REFERENCES models(id),
                    runner TEXT NOT NULL,
                    status TEXT NOT NULL,
                    pid INTEGER,
                    port INTEGER NOT NULL,
                    command_json TEXT NOT NULL,
                    log_path TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS benchmarks (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    model_id TEXT NOT NULL REFERENCES models(id),
                    tasks_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    harness TEXT NOT NULL,
                    harness_version TEXT,
                    command_json TEXT NOT NULL,
                    result_json TEXT,
                    evidence_sha256 TEXT,
                    hardware_json TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS quantum_jobs (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    provider TEXT NOT NULL,
                    backend_mode TEXT NOT NULL,
                    target TEXT NOT NULL,
                    circuit_json TEXT NOT NULL,
                    shots INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    provider_job_id TEXT,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    submitted_at TEXT,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS security_events (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    action TEXT NOT NULL,
                    result TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_models_tenant
                    ON models(tenant_id);
                CREATE INDEX IF NOT EXISTS idx_skills_tenant
                    ON skills(tenant_id);
                CREATE INDEX IF NOT EXISTS idx_runs_tenant
                    ON runs(tenant_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_benchmarks_tenant
                    ON benchmarks(tenant_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_quantum_jobs_tenant
                    ON quantum_jobs(tenant_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_events_tenant
                    ON security_events(tenant_id, created_at DESC);
                """
            )
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @staticmethod
    def _row(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        return dict(row) if row else None

    @staticmethod
    def _decode_json_fields(
        row: Dict[str, Any],
        fields: Iterable[str],
    ) -> Dict[str, Any]:
        for field in fields:
            if field in row:
                value = row.pop(field)
                row[field.removesuffix("_json")] = (
                    json.loads(value) if value is not None else None
                )
        return row

    def create_tenant(self, name: str, slug: str) -> Dict[str, Any]:
        tenant_id = uuid.uuid4().hex
        created_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO tenants (id, name, slug, created_at) "
                "VALUES (?, ?, ?, ?)",
                (tenant_id, name, slug, created_at),
            )
        return {
            "id": tenant_id,
            "name": name,
            "slug": slug,
            "created_at": created_at,
        }

    def get_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            return self._row(
                connection.execute(
                    "SELECT id, name, slug, created_at FROM tenants "
                    "WHERE id = ?",
                    (tenant_id,),
                ).fetchone()
            )

    def get_tenant_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            return self._row(
                connection.execute(
                    "SELECT id, name, slug, created_at FROM tenants "
                    "WHERE slug = ?",
                    (slug,),
                ).fetchone()
            )

    def create_api_key(
        self,
        tenant_id: str,
        name: str,
        scopes: Iterable[str],
    ) -> Dict[str, Any]:
        key_id = uuid.uuid4().hex[:16]
        secret = secrets.token_urlsafe(32)
        raw_key = f"orc_live_{key_id}_{secret}"
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(
            raw_key.encode(),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=32,
        )
        created_at = utc_now()
        normalized_scopes = sorted(set(scopes))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO api_keys (
                    id, tenant_id, name, salt, secret_hash, scopes_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key_id,
                    tenant_id,
                    name,
                    base64.b64encode(salt).decode(),
                    base64.b64encode(digest).decode(),
                    json.dumps(normalized_scopes),
                    created_at,
                ),
            )
        return {
            "id": key_id,
            "tenant_id": tenant_id,
            "name": name,
            "api_key": raw_key,
            "scopes": normalized_scopes,
            "created_at": created_at,
        }

    def authenticate_api_key(self, raw_key: str) -> Optional[Dict[str, Any]]:
        match = API_KEY_PATTERN.fullmatch(raw_key)
        if not match:
            return None
        key_id = match.group(1)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT k.id, k.tenant_id, k.name, k.salt, k.secret_hash,
                       k.scopes_json, k.revoked_at, t.name AS tenant_name,
                       t.slug AS tenant_slug
                FROM api_keys k
                JOIN tenants t ON t.id = k.tenant_id
                WHERE k.id = ?
                """,
                (key_id,),
            ).fetchone()
            if row is None or row["revoked_at"] is not None:
                return None

            digest = hashlib.scrypt(
                raw_key.encode(),
                salt=base64.b64decode(row["salt"]),
                n=2**14,
                r=8,
                p=1,
                dklen=32,
            )
            if not hmac.compare_digest(
                digest,
                base64.b64decode(row["secret_hash"]),
            ):
                return None

            connection.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                (utc_now(), key_id),
            )
            return {
                "key_id": row["id"],
                "tenant_id": row["tenant_id"],
                "key_name": row["name"],
                "tenant_name": row["tenant_name"],
                "tenant_slug": row["tenant_slug"],
                "scopes": json.loads(row["scopes_json"]),
            }

    def list_api_keys(self, tenant_id: str) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, scopes_json, created_at, last_used_at,
                       revoked_at
                FROM api_keys WHERE tenant_id = ?
                ORDER BY created_at DESC
                """,
                (tenant_id,),
            ).fetchall()
        return [
            self._decode_json_fields(dict(row), ["scopes_json"])
            for row in rows
        ]

    def revoke_api_key(self, tenant_id: str, key_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE api_keys SET revoked_at = ?
                WHERE tenant_id = ? AND id = ? AND revoked_at IS NULL
                """,
                (utc_now(), tenant_id, key_id),
            )
        return cursor.rowcount > 0

    def register_model(
        self,
        tenant_id: str,
        name: str,
        owner: str,
        source_repo: Optional[str],
        source_verified: bool,
        model_number: str,
        serial_number: str,
        role_title: Optional[str],
        registry_scope: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        existing = self.get_model_by_repo(tenant_id, source_repo)
        if existing:
            return existing

        model_id = uuid.uuid4().hex
        now = utc_now()
        identity = {
            "model_id": model_id,
            "tenant_id": tenant_id,
            "name": name,
            "owner": owner,
            "source_repo": source_repo,
            "source_verified": source_verified,
            "model_number": model_number,
            "serial_number": serial_number,
            "role_title": role_title,
            "registry_scope": registry_scope,
            "metadata": metadata,
            "created_at": now,
        }
        registration_hash = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO models (
                    id, tenant_id, name, owner, source_repo, source_verified,
                    model_number, serial_number, role_title, registry_scope,
                    registration_hash, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model_id,
                    tenant_id,
                    name,
                    owner,
                    source_repo,
                    int(source_verified),
                    model_number,
                    serial_number,
                    role_title,
                    registry_scope,
                    registration_hash,
                    json.dumps(metadata, sort_keys=True),
                    now,
                    now,
                ),
            )
        return self.get_model(tenant_id, model_id)

    def get_model_by_repo(
        self,
        tenant_id: str,
        source_repo: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if source_repo is None:
            return None
        with self._connect() as connection:
            row = self._row(
                connection.execute(
                    "SELECT * FROM models WHERE tenant_id = ? "
                    "AND source_repo = ?",
                    (tenant_id, source_repo),
                ).fetchone()
            )
        return self._decode_model(row) if row else None

    def get_model(
        self,
        tenant_id: str,
        model_id: str,
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = self._row(
                connection.execute(
                    "SELECT * FROM models WHERE tenant_id = ? AND id = ?",
                    (tenant_id, model_id),
                ).fetchone()
            )
        return self._decode_model(row) if row else None

    def _decode_model(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row = self._decode_json_fields(row, ["metadata_json"])
        row["source_verified"] = bool(row["source_verified"])
        return row

    def list_models(self, tenant_id: str) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM models WHERE tenant_id = ? "
                "ORDER BY CASE WHEN name = 'NayDoeV1' THEN 0 ELSE 1 END, name",
                (tenant_id,),
            ).fetchall()
        return [self._decode_model(dict(row)) for row in rows]

    def update_model_verification(
        self,
        tenant_id: str,
        source_repo: str,
        verified: bool,
        metadata: Dict[str, Any],
    ):
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE models
                SET source_verified = ?, metadata_json = ?, updated_at = ?
                WHERE tenant_id = ? AND source_repo = ?
                """,
                (
                    int(verified),
                    json.dumps(metadata, sort_keys=True),
                    utc_now(),
                    tenant_id,
                    source_repo,
                ),
            )

    def create_skill(
        self,
        tenant_id: str,
        name: str,
        description: str,
        system_prompt: str,
        allowed_models: Iterable[str],
    ) -> Dict[str, Any]:
        skill_id = uuid.uuid4().hex
        now = utc_now()
        models = sorted(set(allowed_models))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO skills (
                    id, tenant_id, name, description, system_prompt,
                    allowed_models_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    skill_id,
                    tenant_id,
                    name,
                    description,
                    system_prompt,
                    json.dumps(models),
                    now,
                    now,
                ),
            )
        return {
            "id": skill_id,
            "tenant_id": tenant_id,
            "name": name,
            "description": description,
            "system_prompt": system_prompt,
            "allowed_models": models,
            "enabled": True,
            "created_at": now,
            "updated_at": now,
        }

    def list_skills(self, tenant_id: str) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM skills WHERE tenant_id = ? ORDER BY name",
                (tenant_id,),
            ).fetchall()
        skills = []
        for row in rows:
            skill = self._decode_json_fields(
                dict(row),
                ["allowed_models_json"],
            )
            skill["enabled"] = bool(skill["enabled"])
            skills.append(skill)
        return skills

    def delete_skill(self, tenant_id: str, skill_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM skills WHERE tenant_id = ? AND id = ?",
                (tenant_id, skill_id),
            )
        return cursor.rowcount > 0

    def create_run(
        self,
        run_id: str,
        tenant_id: str,
        model_id: str,
        runner: str,
        port: int,
        command: List[str],
        log_path: str,
    ):
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs (
                    id, tenant_id, model_id, runner, status, port,
                    command_json, log_path, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'starting', ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    tenant_id,
                    model_id,
                    runner,
                    port,
                    json.dumps(command),
                    log_path,
                    now,
                    now,
                ),
            )

    def update_run(
        self,
        run_id: str,
        status: str,
        pid: Optional[int] = None,
        error: Optional[str] = None,
    ):
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE runs SET status = ?, pid = COALESCE(?, pid),
                    error = ?, updated_at = ? WHERE id = ?
                """,
                (status, pid, error, utc_now(), run_id),
            )

    def get_run(self, tenant_id: str, run_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = self._row(
                connection.execute(
                    "SELECT * FROM runs WHERE tenant_id = ? AND id = ?",
                    (tenant_id, run_id),
                ).fetchone()
            )
        return (
            self._decode_json_fields(row, ["command_json"])
            if row
            else None
        )

    def list_runs(self, tenant_id: str) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runs WHERE tenant_id = ? "
                "ORDER BY created_at DESC LIMIT 100",
                (tenant_id,),
            ).fetchall()
        return [
            self._decode_json_fields(dict(row), ["command_json"])
            for row in rows
        ]

    def create_benchmark(
        self,
        benchmark_id: str,
        tenant_id: str,
        model_id: str,
        tasks: List[str],
        command: List[str],
        harness_version: Optional[str],
        hardware: Dict[str, Any],
    ):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO benchmarks (
                    id, tenant_id, model_id, tasks_json, status, harness,
                    harness_version, command_json, hardware_json, created_at
                ) VALUES (?, ?, ?, ?, 'queued', 'lm-evaluation-harness',
                          ?, ?, ?, ?)
                """,
                (
                    benchmark_id,
                    tenant_id,
                    model_id,
                    json.dumps(tasks),
                    harness_version,
                    json.dumps(command),
                    json.dumps(hardware, sort_keys=True),
                    utc_now(),
                ),
            )

    def update_benchmark(
        self,
        benchmark_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        evidence_sha256: Optional[str] = None,
        error: Optional[str] = None,
        started: bool = False,
        finished: bool = False,
    ):
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE benchmarks
                SET status = ?, result_json = ?, evidence_sha256 = ?,
                    error = ?,
                    started_at = CASE WHEN ? THEN COALESCE(started_at, ?)
                                      ELSE started_at END,
                    finished_at = CASE WHEN ? THEN ? ELSE finished_at END
                WHERE id = ?
                """,
                (
                    status,
                    json.dumps(result, sort_keys=True) if result else None,
                    evidence_sha256,
                    error,
                    int(started),
                    utc_now(),
                    int(finished),
                    utc_now(),
                    benchmark_id,
                ),
            )

    def list_benchmarks(self, tenant_id: str) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT b.*, m.name AS model_name, m.source_repo
                FROM benchmarks b JOIN models m ON m.id = b.model_id
                WHERE b.tenant_id = ?
                ORDER BY b.created_at DESC LIMIT 100
                """,
                (tenant_id,),
            ).fetchall()
        return [
            self._decode_json_fields(
                dict(row),
                [
                    "tasks_json",
                    "command_json",
                    "result_json",
                    "hardware_json",
                ],
            )
            for row in rows
        ]

    def get_benchmark(
        self,
        tenant_id: str,
        benchmark_id: str,
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT b.*, m.name AS model_name, m.source_repo
                FROM benchmarks b JOIN models m ON m.id = b.model_id
                WHERE b.tenant_id = ? AND b.id = ?
                """,
                (tenant_id, benchmark_id),
            ).fetchone()
        if row is None:
            return None
        return self._decode_json_fields(
            dict(row),
            [
                "tasks_json",
                "command_json",
                "result_json",
                "hardware_json",
            ],
        )

    def create_quantum_job(
        self,
        tenant_id: str,
        provider: str,
        backend_mode: str,
        target: str,
        circuit: Dict[str, Any],
        shots: int,
    ) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex
        created_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO quantum_jobs (
                    id, tenant_id, provider, backend_mode, target,
                    circuit_json, shots, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?)
                """,
                (
                    job_id,
                    tenant_id,
                    provider,
                    backend_mode,
                    target,
                    json.dumps(circuit, sort_keys=True),
                    shots,
                    created_at,
                ),
            )
        return {
            "id": job_id,
            "tenant_id": tenant_id,
            "provider": provider,
            "backend_mode": backend_mode,
            "target": target,
            "circuit": circuit,
            "shots": shots,
            "status": "queued",
            "created_at": created_at,
        }

    def update_quantum_job(
        self,
        job_id: str,
        status: str,
        provider_job_id: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        now = utc_now()
        terminal = status in {"completed", "failed", "cancelled"}
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE quantum_jobs
                SET status = ?, provider_job_id = COALESCE(?, provider_job_id),
                    result_json = ?, error = ?,
                    submitted_at = CASE
                        WHEN ? = 'submitted' THEN COALESCE(submitted_at, ?)
                        ELSE submitted_at END,
                    completed_at = CASE WHEN ? THEN ? ELSE completed_at END
                WHERE id = ?
                """,
                (
                    status,
                    provider_job_id,
                    json.dumps(result, sort_keys=True) if result else None,
                    error,
                    status,
                    now,
                    int(terminal),
                    now,
                    job_id,
                ),
            )

    def list_quantum_jobs(self, tenant_id: str) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM quantum_jobs WHERE tenant_id = ? "
                "ORDER BY created_at DESC LIMIT 100",
                (tenant_id,),
            ).fetchall()
        return [
            self._decode_json_fields(
                dict(row),
                ["circuit_json", "result_json"],
            )
            for row in rows
        ]

    def get_quantum_job(
        self,
        tenant_id: str,
        job_id: str,
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM quantum_jobs WHERE tenant_id = ? AND id = ?",
                (tenant_id, job_id),
            ).fetchone()
        if row is None:
            return None
        return self._decode_json_fields(
            dict(row),
            ["circuit_json", "result_json"],
        )

    def record_security_event(
        self,
        tenant_id: Optional[str],
        event: Dict[str, Any],
    ):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO security_events (
                    id, tenant_id, event_type, source, severity, actor,
                    resource, action, result, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["event_id"],
                    tenant_id,
                    event["event_type"],
                    event["source"],
                    event["severity"],
                    event["actor"],
                    event["resource"],
                    event["action"],
                    event["result"],
                    json.dumps(event.get("details", {}), sort_keys=True),
                    event.get("created_at", utc_now()),
                ),
            )

    def list_security_events(
        self,
        tenant_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM security_events
                WHERE tenant_id = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (tenant_id, min(max(limit, 1), 500)),
            ).fetchall()
        return [
            self._decode_json_fields(dict(row), ["details_json"])
            for row in rows
        ]
