"""Allowlisted model process control for the VPS orchestration service."""

import os
from pathlib import Path
import shutil
import signal
import subprocess
import threading
from typing import Dict, List
import uuid

from orchestration.database import OrchestrationDatabase
from orchestration.huggingface import validate_repo_id


class ModelRunnerManager:
    """Start and stop supported model servers without accepting raw commands."""

    def __init__(
        self,
        database: OrchestrationDatabase,
        runtime_directory: str,
        max_concurrent_runs: int = 2,
    ):
        self.database = database
        self.runtime_directory = Path(runtime_directory).expanduser().resolve()
        self.runtime_directory.mkdir(parents=True, exist_ok=True)
        self.max_concurrent_runs = max(1, max_concurrent_runs)
        self._processes: Dict[str, subprocess.Popen] = {}
        self._ports: Dict[str, int] = {}
        self._lock = threading.RLock()

    @staticmethod
    def build_command(
        runner: str,
        repo_id: str,
        port: int,
    ) -> List[str]:
        validate_repo_id(repo_id)
        if not 1024 <= port <= 65535:
            raise ValueError("Port must be between 1024 and 65535")
        if runner == "vllm":
            return [
                "vllm",
                "serve",
                repo_id,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ]
        if runner == "llama_cpp":
            return [
                "llama-server",
                "-hf",
                repo_id,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ]
        raise ValueError("Unsupported model runner")

    @staticmethod
    def available_runners() -> Dict[str, bool]:
        return {
            "vllm": shutil.which("vllm") is not None,
            "llama_cpp": shutil.which("llama-server") is not None,
        }

    def start(
        self,
        tenant_id: str,
        model: Dict,
        runner: str,
        port: int,
    ) -> Dict:
        repo_id = model.get("source_repo")
        if not repo_id:
            raise ValueError("Model has no runnable repository")
        command = self.build_command(runner, repo_id, port)
        if shutil.which(command[0]) is None:
            raise RuntimeError(
                f"{command[0]} is not installed on this VPS"
            )

        with self._lock:
            self._refresh_processes()
            if len(self._processes) >= self.max_concurrent_runs:
                raise RuntimeError("Concurrent model runner limit reached")
            if port in self._ports.values():
                raise RuntimeError("Port is already used by a model runner")

            run_id = uuid.uuid4().hex
            log_path = self.runtime_directory / f"{run_id}.log"
            self.database.create_run(
                run_id,
                tenant_id,
                model["id"],
                runner,
                port,
                command,
                str(log_path),
            )
            try:
                with log_path.open("ab") as log_file:
                    process = subprocess.Popen(
                        command,
                        cwd=self.runtime_directory,
                        stdin=subprocess.DEVNULL,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        env=self._runner_environment(),
                        start_new_session=True,
                    )
            except Exception as exc:
                self.database.update_run(
                    run_id,
                    "failed",
                    error=str(exc),
                )
                raise

            self._processes[run_id] = process
            self._ports[run_id] = port
            self.database.update_run(
                run_id,
                "running",
                pid=process.pid,
            )
        return self.database.get_run(tenant_id, run_id)

    @staticmethod
    def _runner_environment() -> Dict[str, str]:
        allowed_names = {
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
            if name in allowed_names
        }

    def stop(self, tenant_id: str, run_id: str) -> Dict:
        run = self.database.get_run(tenant_id, run_id)
        if run is None:
            raise KeyError("Model run not found")

        with self._lock:
            process = self._processes.get(run_id)
            if process is None:
                raise RuntimeError(
                    "Runner is not managed by this service process"
                )
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
            self._processes.pop(run_id, None)
            self._ports.pop(run_id, None)
            self.database.update_run(run_id, "stopped")
        return self.database.get_run(tenant_id, run_id)

    def _refresh_processes(self):
        for run_id, process in list(self._processes.items()):
            return_code = process.poll()
            if return_code is not None:
                status = "stopped" if return_code == 0 else "failed"
                error = (
                    None
                    if return_code == 0
                    else f"Runner exited with status {return_code}"
                )
                self.database.update_run(
                    run_id,
                    status,
                    error=error,
                )
                del self._processes[run_id]
                self._ports.pop(run_id, None)

    def list_runs(self, tenant_id: str) -> List[Dict]:
        with self._lock:
            self._refresh_processes()
        return self.database.list_runs(tenant_id)

    def shutdown(self):
        """Stop child processes created by this service instance."""
        with self._lock:
            for run_id, process in list(self._processes.items()):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                self.database.update_run(run_id, "stopped")
            self._processes.clear()
            self._ports.clear()
