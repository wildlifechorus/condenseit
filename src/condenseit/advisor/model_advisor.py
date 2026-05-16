"""Recommend Ollama models for this machine."""

from __future__ import annotations

import httpx

from condenseit.advisor.benchmark import benchmark_model
from condenseit.advisor.hardware_detect import detect_hardware
from condenseit.advisor.model_registry import MODELS, models_for_ram
from condenseit.store.database import ContentStore


class ModelAdvisor:
    def __init__(
        self,
        store: ContentStore,
        ollama_host: str = "http://localhost:11434",
    ) -> None:
        self.store = store
        self.ollama_host = ollama_host.rstrip("/")

    def recommend(self, current_model: str) -> dict[str, object]:
        hw = detect_hardware()
        candidates = models_for_ram(hw.ram_gb)
        if not candidates:
            candidates = [MODELS[0]]

        best = max(candidates, key=lambda m: float(m["ram_gb"]))
        installed = self._list_installed()
        return {
            "hardware": hw.to_dict(),
            "current_model": current_model,
            "recommended_model": best["name"],
            "reason": (
                f"Based on {hw.ram_gb:.0f} GB RAM, "
                f"{best['name']} balances quality and fit."
            ),
            "installed_models": installed,
            "candidates": candidates,
        }

    def benchmark(self, model: str) -> dict[str, object]:
        return benchmark_model(self.store, self.ollama_host, model)

    def _list_installed(self) -> list[str]:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.ollama_host}/api/tags")
                resp.raise_for_status()
                models = resp.json().get("models", [])
                return [m.get("name", "") for m in models]
        except httpx.HTTPError:
            return []
