"""FastAPI application for the Orcai25 VPS orchestration service."""

from collections import defaultdict, deque
from contextlib import asynccontextmanager
import hashlib
import os
from pathlib import Path
import threading
import time
from typing import Dict, List, Optional, Set

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from orchestration.service import OrchestrationService


class APIKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: List[str] = Field(min_length=1, max_length=6)


class SkillCreate(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    description: str = Field(min_length=1, max_length=500)
    system_prompt: str = Field(min_length=1, max_length=12000)
    allowed_models: List[str] = Field(min_length=1, max_length=100)


class ModelRunCreate(BaseModel):
    model_id: str = Field(min_length=32, max_length=32)
    runner: str
    port: int = Field(ge=1024, le=65535)


class BenchmarkCreate(BaseModel):
    model_id: str = Field(min_length=32, max_length=32)
    tasks: List[str] = Field(min_length=1, max_length=6)
    limit: Optional[int] = Field(default=None, ge=1, le=10000)


class QuantumJobCreate(BaseModel):
    provider: str
    backend_mode: str
    target: Optional[str] = Field(default=None, max_length=128)
    circuit: Dict
    shots: int = Field(default=1024, ge=1, le=10000)
    confirm_hardware: bool = False


class SlidingWindowRateLimiter:
    """Per-key in-memory protection for a single VPS process."""

    def __init__(self, requests_per_minute: int = 120):
        self.limit = max(10, requests_per_minute)
        self._requests = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        cutoff = time.monotonic() - 60
        with self._lock:
            requests = self._requests[key]
            while requests and requests[0] < cutoff:
                requests.popleft()
            if len(requests) >= self.limit:
                return False
            requests.append(time.monotonic())
            return True


def create_app(
    service: Optional[OrchestrationService] = None,
) -> FastAPI:
    service_instance = service or OrchestrationService()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        service_instance.runners.shutdown()

    app = FastAPI(
        title="NayDoeV1 Orchestration SaaS",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.service = service_instance
    app.state.rate_limiter = SlidingWindowRateLimiter(
        int(os.environ.get("ORCAI_RATE_LIMIT_PER_MINUTE", "120"))
    )

    allowed_hosts = [
        host.strip()
        for host in os.environ.get(
            "ORCAI_ALLOWED_HOSTS",
            "127.0.0.1,localhost,testserver",
        ).split(",")
        if host.strip()
    ]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > 1024 * 1024:
                    return JSONResponse(
                        {"detail": "Request body is too large"},
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    )
            except ValueError:
                return JSONResponse(
                    {"detail": "Invalid Content-Length"},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(KeyError)
    async def key_error_handler(_: Request, exc: KeyError):
        return JSONResponse(
            {"detail": str(exc).strip("'")},
            status_code=404,
        )

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(_: Request, exc: RuntimeError):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    async def principal(
        request: Request,
        x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
        authorization: Optional[str] = Header(default=None),
    ) -> Dict:
        raw_key = x_api_key
        if not raw_key and authorization:
            scheme, _, value = authorization.partition(" ")
            if scheme.casefold() == "bearer":
                raw_key = value
        if not raw_key:
            raise HTTPException(status_code=401, detail="API key required")

        fingerprint = hashlib.sha256(raw_key.encode()).hexdigest()[:24]
        client_ip = request.client.host if request.client else "unknown"
        limiter = request.app.state.rate_limiter
        if not limiter.allow(f"{client_ip}:{fingerprint}"):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        authenticated = service_instance.database.authenticate_api_key(raw_key)
        if not authenticated:
            raise HTTPException(status_code=401, detail="Invalid API key")
        try:
            service_instance.authorize_request(
                authenticated,
                client_ip,
                request.url.path,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return authenticated

    def require_scopes(*required_scopes: str):
        required: Set[str] = set(required_scopes)

        async def dependency(
            authenticated: Dict = Depends(principal),
        ) -> Dict:
            scopes = set(authenticated["scopes"])
            if "admin" not in scopes and not required.issubset(scopes):
                raise HTTPException(
                    status_code=403,
                    detail="API key lacks the required scope",
                )
            return authenticated

        return dependency

    @app.get("/healthz")
    async def health():
        return {"status": "ok", "service": "naydoev1-orchestrator"}

    @app.get("/api/v1/public/naydoev1")
    async def public_profile():
        profile = service_instance.public_naydoev1_profile()
        if not profile:
            raise HTTPException(
                status_code=404,
                detail="NayDoeV1 has not been bootstrapped",
            )
        return profile

    @app.get("/api/v1/auth/whoami")
    async def whoami(authenticated: Dict = Depends(principal)):
        return authenticated

    @app.post("/api/v1/auth/keys", status_code=201)
    async def create_key(
        payload: APIKeyCreate,
        authenticated: Dict = Depends(require_scopes("admin")),
    ):
        return service_instance.create_api_key(
            authenticated["tenant_id"],
            payload.name,
            payload.scopes,
        )

    @app.get("/api/v1/auth/keys")
    async def list_keys(
        authenticated: Dict = Depends(require_scopes("admin")),
    ):
        return service_instance.database.list_api_keys(
            authenticated["tenant_id"]
        )

    @app.delete("/api/v1/auth/keys/{key_id}", status_code=204)
    async def revoke_key(
        key_id: str,
        authenticated: Dict = Depends(require_scopes("admin")),
    ):
        if not service_instance.database.revoke_api_key(
            authenticated["tenant_id"],
            key_id,
        ):
            raise KeyError("API key not found or already revoked")

    @app.get("/api/v1/status")
    async def orchestration_status(
        authenticated: Dict = Depends(require_scopes("read")),
    ):
        return service_instance.status(authenticated["tenant_id"])

    @app.get("/api/v1/models")
    async def list_models(
        authenticated: Dict = Depends(require_scopes("read")),
    ):
        return service_instance.database.list_models(
            authenticated["tenant_id"]
        )

    @app.post("/api/v1/models/refresh")
    async def refresh_models(
        authenticated: Dict = Depends(require_scopes("admin")),
    ):
        return service_instance.refresh_huggingface(
            authenticated["tenant_id"]
        )

    @app.get("/api/v1/models/{model_id}/commands")
    async def model_commands(
        model_id: str,
        port: int = 8001,
        authenticated: Dict = Depends(require_scopes("read")),
    ):
        return service_instance.model_commands(
            authenticated["tenant_id"],
            model_id,
            port,
        )

    @app.get("/api/v1/skills")
    async def list_skills(
        authenticated: Dict = Depends(require_scopes("read")),
    ):
        return service_instance.database.list_skills(
            authenticated["tenant_id"]
        )

    @app.post("/api/v1/skills", status_code=201)
    async def create_skill(
        payload: SkillCreate,
        authenticated: Dict = Depends(require_scopes("skills")),
    ):
        return service_instance.create_skill(
            authenticated["tenant_id"],
            payload.name,
            payload.description,
            payload.system_prompt,
            payload.allowed_models,
        )

    @app.delete("/api/v1/skills/{skill_id}", status_code=204)
    async def delete_skill(
        skill_id: str,
        authenticated: Dict = Depends(require_scopes("skills")),
    ):
        service_instance.delete_skill(
            authenticated["tenant_id"],
            skill_id,
        )

    @app.get("/api/v1/runners")
    async def list_runners(
        authenticated: Dict = Depends(require_scopes("read")),
    ):
        return {
            "available": service_instance.runners.available_runners(),
            "runs": service_instance.runners.list_runs(
                authenticated["tenant_id"]
            ),
        }

    @app.post("/api/v1/runners", status_code=201)
    async def start_runner(
        payload: ModelRunCreate,
        authenticated: Dict = Depends(require_scopes("control")),
    ):
        return service_instance.start_model(
            authenticated["tenant_id"],
            payload.model_id,
            payload.runner,
            payload.port,
        )

    @app.post("/api/v1/runners/{run_id}/stop")
    async def stop_runner(
        run_id: str,
        authenticated: Dict = Depends(require_scopes("control")),
    ):
        return service_instance.stop_model(
            authenticated["tenant_id"],
            run_id,
        )

    @app.get("/api/v1/benchmarks")
    async def list_benchmarks(
        authenticated: Dict = Depends(require_scopes("read")),
    ):
        return service_instance.database.list_benchmarks(
            authenticated["tenant_id"]
        )

    @app.post("/api/v1/benchmarks", status_code=202)
    async def start_benchmark(
        payload: BenchmarkCreate,
        authenticated: Dict = Depends(require_scopes("benchmark")),
    ):
        return service_instance.start_benchmark(
            authenticated["tenant_id"],
            payload.model_id,
            payload.tasks,
            payload.limit,
        )

    @app.get("/api/v1/quantum/providers")
    async def quantum_providers(
        _: Dict = Depends(require_scopes("read")),
    ):
        return service_instance.quantum.provider_status()

    @app.get("/api/v1/quantum/jobs")
    async def quantum_jobs(
        authenticated: Dict = Depends(require_scopes("read")),
    ):
        return service_instance.database.list_quantum_jobs(
            authenticated["tenant_id"]
        )

    @app.post("/api/v1/quantum/jobs", status_code=202)
    async def submit_quantum_job(
        payload: QuantumJobCreate,
        authenticated: Dict = Depends(require_scopes("quantum")),
    ):
        return service_instance.submit_quantum_job(
            authenticated["tenant_id"],
            payload.provider,
            payload.backend_mode,
            payload.target,
            payload.circuit,
            payload.shots,
            payload.confirm_hardware,
        )

    @app.post("/api/v1/quantum/jobs/{job_id}/refresh")
    async def refresh_quantum_job(
        job_id: str,
        authenticated: Dict = Depends(require_scopes("quantum")),
    ):
        return service_instance.quantum.refresh_ionq_job(
            authenticated["tenant_id"],
            job_id,
        )

    @app.get("/api/v1/events")
    async def security_events(
        limit: int = 100,
        authenticated: Dict = Depends(require_scopes("read")),
    ):
        return service_instance.database.list_security_events(
            authenticated["tenant_id"],
            limit,
        )

    static_directory = Path(__file__).resolve().parent / "static"
    app.mount(
        "/assets",
        StaticFiles(directory=static_directory),
        name="assets",
    )

    @app.get("/", include_in_schema=False)
    async def website():
        return FileResponse(static_directory / "index.html")

    return app
