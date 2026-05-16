"""Start and stop a local Ollama server around pipeline runs."""

from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OllamaLifecycle:
    """Context manager that starts Ollama if needed and stops it after."""

    def __init__(
        self,
        host: str = "http://localhost:11434",
        startup_timeout: int = 60,
        manage: bool = True,
    ) -> None:
        self.host = host.rstrip("/")
        self.health_url = f"{self.host}/api/tags"
        self.startup_timeout = startup_timeout
        self.manage = manage
        self._process: subprocess.Popen[bytes] | None = None
        self._started_by_us = False

    def __enter__(self) -> OllamaLifecycle:
        if not self.manage:
            self._wait_until_ready()
            return self
        if self.is_running():
            logger.info("Ollama already running at %s", self.host)
            return self
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        if self._started_by_us:
            self.stop()
        return False

    def is_running(self) -> bool:
        try:
            response = httpx.get(self.health_url, timeout=2.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def start(self) -> None:
        if self.is_running():
            return
        binary = shutil.which("ollama")
        if not binary:
            raise RuntimeError(
                "ollama binary not found. Install Ollama or set OLLAMA_HOST "
                "to a running server (e.g. Docker Compose).",
            )
        env = os.environ.copy()
        if self.host != "http://localhost:11434":
            env["OLLAMA_HOST"] = self.host
        logger.info("Starting Ollama subprocess")
        self._process = subprocess.Popen(
            [binary, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        self._started_by_us = True
        self._wait_until_ready()

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            logger.info("Stopping Ollama subprocess")
            self._process.send_signal(signal.SIGTERM)
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        self._started_by_us = False

    def _wait_until_ready(self) -> None:
        deadline = time.time() + self.startup_timeout
        while time.time() < deadline:
            if self.is_running():
                return
            time.sleep(0.5)
        msg = f"Ollama not ready at {self.host} after {self.startup_timeout}s"
        raise TimeoutError(msg)
