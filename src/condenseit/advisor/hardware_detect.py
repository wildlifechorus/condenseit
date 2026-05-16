"""Host hardware detection for model recommendations."""

from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass


@dataclass
class HardwareProfile:
    os_name: str
    arch: str
    cpu_count: int
    ram_gb: float
    gpu_hint: str

    def to_dict(self) -> dict[str, str | int | float]:
        return {
            "os": self.os_name,
            "arch": self.arch,
            "cpu_count": self.cpu_count,
            "ram_gb": round(self.ram_gb, 1),
            "gpu_hint": self.gpu_hint,
        }


def detect_hardware() -> HardwareProfile:
    ram_gb = _ram_gb()
    gpu = "unknown"
    system = platform.system().lower()
    if system == "darwin":
        gpu = "apple-metal"
    elif os.path.exists("/dev/nvidia0"):
        gpu = "nvidia"
    return HardwareProfile(
        os_name=platform.system(),
        arch=platform.machine(),
        cpu_count=os.cpu_count() or 4,
        ram_gb=ram_gb,
        gpu_hint=gpu,
    )


def _ram_gb() -> float:
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            return int(out.strip()) / (1024**3)
        if system == "Linux":
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return kb / (1024**2)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return 8.0
