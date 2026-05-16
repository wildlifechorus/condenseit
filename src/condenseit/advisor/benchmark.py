"""Ollama latency benchmark and persistence."""

from __future__ import annotations

import time
from typing import Any

import httpx

from condenseit.store.database import ContentStore


def benchmark_model(
    store: ContentStore,
    ollama_host: str,
    model: str,
) -> dict[str, Any]:
    """Run a short generate job and store timing in ``benchmarks`` table."""
    host = ollama_host.rstrip("/")
    prompt = "Summarize: Kubernetes released a security patch."
    start = time.time()
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 80},
            },
        )
        resp.raise_for_status()
        data = resp.json()
    elapsed = time.time() - start
    text = data.get("response", "")
    tokens = len(text.split())
    tps = tokens / elapsed if elapsed > 0 else 0
    result = {
        "model": model,
        "elapsed_s": round(elapsed, 2),
        "approx_tokens": tokens,
        "tokens_per_sec": round(tps, 1),
    }
    if "benchmarks" not in store.db.table_names():
        store.db["benchmarks"].create(
            {
                "id": int,
                "model": str,
                "elapsed_s": float,
                "approx_tokens": int,
                "tokens_per_sec": float,
                "run_at": str,
            },
            pk="id",
        )
    store.db["benchmarks"].insert(
        {**result, "run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
    )
    return result
