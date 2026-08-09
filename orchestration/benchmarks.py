"""Evidence-preserving lm-evaluation-harness benchmark execution."""

import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import threading
from typing import Callable, Dict, List, Optional
import uuid

from orchestration.database import OrchestrationDatabase
from orchestration.huggingface import validate_repo_id


ALLOWED_BENCHMARK_TASKS = {
    "arc_challenge",
    "gsm8k",
    "hellaswag",
    "mmlu",
    "truthfulqa_mc2",
    "winogrande",
}
REVISION_PATTERN = re.compile(r"^[A-Za-z0-9._/-]{1,128}$")


class BenchmarkManager:
    """Run standard benchmarks and retain the unmodified result evidence."""

    def __init__(
        self,
        database: OrchestrationDatabase,
        runtime_directory: str,
        event_callback: Optional[Callable[[str, str, Dict], None]] = None,
    ):
        self.database = database
        self.runtime_directory = Path(runtime_directory).expanduser().resolve()
        self.runtime_directory.mkdir(parents=True, exist_ok=True)
        self.event_callback = event_callback
        self._processes: Dict[str, subprocess.Popen] = {}
        self._tenants: Dict[str, str] = {}
        self._lock = threading.Lock()

    @staticmethod
    def harness_version() -> Optional[str]:
        try:
            return metadata.version("lm_eval")
        except metadata.PackageNotFoundError:
            return None

    @staticmethod
    def build_command(
        repo_id: str,
        tasks: List[str],
        output_path: str,
        revision: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[str]:
        validate_repo_id(repo_id)
        if not tasks or any(task not in ALLOWED_BENCHMARK_TASKS for task in tasks):
            raise ValueError("One or more benchmark tasks are not allowlisted")
        model_args = f"pretrained={repo_id}"
        if revision:
            if not REVISION_PATTERN.fullmatch(revision):
                raise ValueError("Invalid model revision")
            model_args += f",revision={revision}"

        command = [
            "lm_eval",
            "--model",
            "hf",
            "--model_args",
            model_args,
            "--tasks",
            ",".join(sorted(set(tasks))),
            "--batch_size",
            "auto",
            "--output_path",
            output_path,
            "--log_samples",
        ]
        if limit is not None:
            if not 1 <= limit <= 10000:
                raise ValueError("Benchmark limit must be between 1 and 10000")
            command.extend(["--limit", str(limit)])
        return command

    def start(
        self,
        tenant_id: str,
        model: Dict,
        tasks: List[str],
        limit: Optional[int] = None,
    ) -> Dict:
        repo_id = model.get("source_repo")
        if not repo_id:
            raise ValueError("Model has no benchmarkable repository")

        benchmark_id = uuid.uuid4().hex
        output_directory = self.runtime_directory / benchmark_id
        output_directory.mkdir(mode=0o700)
        output_path = output_directory / "results.json"
        revision = model.get("metadata", {}).get("revision")
        command = self.build_command(
            repo_id,
            tasks,
            str(output_path),
            revision=revision,
            limit=limit,
        )
        hardware = {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "cuda_visible_devices": os.environ.get(
                "CUDA_VISIBLE_DEVICES",
                "not_set",
            ),
        }
        self.database.create_benchmark(
            benchmark_id,
            tenant_id,
            model["id"],
            sorted(set(tasks)),
            command,
            self.harness_version(),
            hardware,
        )
        self._tenants[benchmark_id] = tenant_id

        if shutil.which("lm_eval") is None:
            error = (
                "lm-evaluation-harness is not installed; no score was "
                "fabricated"
            )
            self.database.update_benchmark(
                benchmark_id,
                "unavailable",
                error=error,
                finished=True,
            )
            self._emit(benchmark_id, "unavailable", {"error": error})
            return self.database.get_benchmark(tenant_id, benchmark_id)

        log_path = output_directory / "benchmark.log"
        try:
            with log_path.open("ab") as log_file:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    env=self._benchmark_environment(),
                    start_new_session=True,
                )
        except Exception as exc:
            self.database.update_benchmark(
                benchmark_id,
                "failed",
                error=str(exc),
                finished=True,
            )
            raise

        with self._lock:
            self._processes[benchmark_id] = process
        self.database.update_benchmark(
            benchmark_id,
            "running",
            started=True,
        )
        self._emit(benchmark_id, "running", {"model": repo_id})
        threading.Thread(
            target=self._collect_result,
            args=(benchmark_id, process, output_path),
            daemon=True,
        ).start()
        return self.database.get_benchmark(tenant_id, benchmark_id)

    @staticmethod
    def _benchmark_environment() -> Dict[str, str]:
        allowed = {
            "PATH",
            "HOME",
            "HF_HOME",
            "HF_TOKEN",
            "CUDA_VISIBLE_DEVICES",
            "LD_LIBRARY_PATH",
        }
        return {
            name: value
            for name, value in os.environ.items()
            if name in allowed
        }

    def _collect_result(
        self,
        benchmark_id: str,
        process: subprocess.Popen,
        output_path: Path,
    ):
        return_code = process.wait()
        with self._lock:
            self._processes.pop(benchmark_id, None)
        if return_code != 0:
            error = f"lm-evaluation-harness exited with status {return_code}"
            self.database.update_benchmark(
                benchmark_id,
                "failed",
                error=error,
                finished=True,
            )
            self._emit(benchmark_id, "failed", {"error": error})
            return

        candidates = [output_path]
        candidates.extend(output_path.parent.rglob("*.json"))
        result_path = next(
            (path for path in candidates if path.is_file()),
            None,
        )
        if result_path is None:
            error = "Benchmark completed without a JSON result file"
            self.database.update_benchmark(
                benchmark_id,
                "failed",
                error=error,
                finished=True,
            )
            self._emit(benchmark_id, "failed", {"error": error})
            return

        try:
            raw_result = result_path.read_bytes()
            result = json.loads(raw_result)
        except (OSError, json.JSONDecodeError) as exc:
            self.database.update_benchmark(
                benchmark_id,
                "failed",
                error=f"Could not read benchmark evidence: {exc}",
                finished=True,
            )
            return

        evidence_hash = hashlib.sha256(raw_result).hexdigest()
        self.database.update_benchmark(
            benchmark_id,
            "completed",
            result=result,
            evidence_sha256=evidence_hash,
            finished=True,
        )
        self._emit(
            benchmark_id,
            "completed",
            {"evidence_sha256": evidence_hash},
        )

    def _emit(self, benchmark_id: str, status: str, details: Dict):
        if self.event_callback:
            self.event_callback(
                benchmark_id,
                status,
                {
                    **details,
                    "tenant_id": self._tenants.get(benchmark_id),
                },
            )
