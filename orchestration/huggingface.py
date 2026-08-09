"""Live Hugging Face discovery and safe copy/paste command generation."""

import json
import re
import shlex
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REPO_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}/"
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}$"
)
OWNER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


def validate_repo_id(repo_id: str) -> str:
    if not REPO_ID_PATTERN.fullmatch(repo_id):
        raise ValueError("Invalid Hugging Face repository ID")
    return repo_id


class HuggingFaceCatalog:
    """Fetch public models directly from the official Hub API."""

    API_URL = "https://huggingface.co/api/models"
    MAX_RESPONSE_BYTES = 2 * 1024 * 1024

    def __init__(
        self,
        owner: str = "NaTo10000",
        timeout_seconds: int = 10,
        opener: Optional[Callable] = None,
    ):
        if not OWNER_PATTERN.fullmatch(owner):
            raise ValueError("Invalid Hugging Face owner")
        self.owner = owner
        self.timeout_seconds = timeout_seconds
        self._urlopen = opener or urlopen

    def discover(self) -> List[Dict[str, Any]]:
        query = urlencode({"author": self.owner, "limit": 100})
        request = Request(
            f"{self.API_URL}?{query}",
            headers={
                "Accept": "application/json",
                "User-Agent": "Orcai25-Orchestrator/1.0",
            },
        )
        with self._urlopen(request, timeout=self.timeout_seconds) as response:
            payload = response.read(self.MAX_RESPONSE_BYTES + 1)
        if len(payload) > self.MAX_RESPONSE_BYTES:
            raise ValueError("Hugging Face response exceeded size limit")

        data = json.loads(payload)
        if not isinstance(data, list):
            raise ValueError("Unexpected Hugging Face response")

        models = []
        for item in data:
            if not isinstance(item, dict):
                continue
            repo_id = item.get("id") or item.get("modelId")
            if not isinstance(repo_id, str):
                continue
            try:
                validate_repo_id(repo_id)
            except ValueError:
                continue
            owner, _, name = repo_id.partition("/")
            if owner.casefold() != self.owner.casefold():
                continue
            models.append(
                {
                    "repo_id": repo_id,
                    "name": name,
                    "owner": owner,
                    "pipeline_tag": item.get("pipeline_tag"),
                    "library_name": item.get("library_name"),
                    "revision": item.get("sha"),
                    "downloads": int(item.get("downloads") or 0),
                    "likes": int(item.get("likes") or 0),
                    "last_modified": item.get("lastModified"),
                    "tags": [
                        tag
                        for tag in item.get("tags", [])
                        if isinstance(tag, str)
                    ][:100],
                    "source": "huggingface_live_api",
                }
            )
        return sorted(
            models,
            key=lambda model: (
                -model["downloads"],
                model["repo_id"].casefold(),
            ),
        )

    @staticmethod
    def commands(repo_id: str, port: int = 8001) -> Dict[str, str]:
        """Return shell-quoted commands for display, never for shell execution."""
        validate_repo_id(repo_id)
        if not 1024 <= port <= 65535:
            raise ValueError("Port must be between 1024 and 65535")
        quoted_repo = shlex.quote(repo_id)
        directory = re.sub(r"[^A-Za-z0-9._-]", "-", repo_id)
        quoted_directory = shlex.quote(f"./models/{directory}")
        return {
            "download": (
                f"hf download {quoted_repo} --local-dir {quoted_directory}"
            ),
            "serve_vllm": (
                f"vllm serve {quoted_repo} --host 127.0.0.1 "
                f"--port {port}"
            ),
            "serve_llama_cpp": (
                f"llama-server -hf {quoted_repo} --host 127.0.0.1 "
                f"--port {port}"
            ),
            "benchmark": (
                "lm_eval --model hf "
                f"--model_args pretrained={quoted_repo} "
                "--tasks arc_challenge,hellaswag,gsm8k "
                "--batch_size auto"
            ),
        }
