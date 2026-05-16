"""Deploy digests to a VPS via rsync."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from condenseit.config import VpsConfig

logger = logging.getLogger(__name__)


class VpsDeployer:
    def __init__(self, config: VpsConfig) -> None:
        self.config = config

    def deploy(self, local_dir: str | Path) -> dict[str, str]:
        if not self.config.enabled:
            return {"status": "disabled_in_config", "reason": "vps.enabled is false"}
        if not self.config.host.strip():
            return {"status": "missing_host", "reason": "vps.host is empty"}

        local = Path(local_dir).expanduser()
        if not local.exists():
            return {"status": "error", "error": f"missing {local}"}

        ssh_key = Path(self.config.ssh_key).expanduser()
        dest = f"{self.config.host}:{self.config.path}"
        cmd = [
            "rsync",
            "-avz",
            "--delete",
            "-e",
            (
                f"ssh -i {ssh_key} -p {self.config.ssh_port} "
                "-o StrictHostKeyChecking=accept-new"
            ),
            f"{local}/",
            dest,
        ]
        logger.info("Rsync to %s", dest)
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return {"status": "ok", "destination": dest}
