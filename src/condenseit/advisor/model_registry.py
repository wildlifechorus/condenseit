"""Known Ollama models and RAM requirements (GB)."""

from __future__ import annotations

MODELS: list[dict[str, str | float]] = [
    {"name": "llama3.2:3b", "ram_gb": 3.0, "quality": "good", "speed": "fast"},
    {"name": "llama3.1:8b", "ram_gb": 6.5, "quality": "good", "speed": "fast"},
    {"name": "mistral:7b", "ram_gb": 6.0, "quality": "good", "speed": "fast"},
    {"name": "qwen2.5:14b", "ram_gb": 10.0, "quality": "very good", "speed": "medium"},
    {"name": "llama3.1:70b", "ram_gb": 28.0, "quality": "excellent", "speed": "slow"},
]


def models_for_ram(ram_gb: float) -> list[dict[str, str | float]]:
    headroom = 4.0
    usable = max(ram_gb - headroom, 2.0)
    return [m for m in MODELS if float(m["ram_gb"]) <= usable]
