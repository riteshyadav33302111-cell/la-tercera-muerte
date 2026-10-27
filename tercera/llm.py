"""
Thin Ollama wrapper. Swap models in config.toml — the ghost is not
tied to any single provider.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Generator, Optional

import httpx

from .config import get_config

_cfg = get_config()


def _base_url() -> str:
    return _cfg.get("ollama", {}).get("base_url", "http://localhost:11434")


def chat(
    messages: list[dict],
    model: Optional[str] = None,
    stream: bool = False,
    temperature: float = 0.85,
    **kwargs,
) -> str | Generator[str, None, None]:
    """Send a chat completion request to Ollama."""
    if model is None:
        model = _cfg.get("models", {}).get("persona_model", "llama3.1:8b")

    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": {"temperature": temperature, **kwargs},
    }

    url = f"{_base_url()}/api/chat"

    if stream:
        return _stream_chat(url, payload)
    else:
        resp = httpx.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["message"]["content"]


def _stream_chat(url: str, payload: dict) -> Generator[str, None, None]:
    with httpx.stream("POST", url, json=payload, timeout=120) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if line:
                data = json.loads(line)
                if "message" in data:
                    yield data["message"]["content"]
                if data.get("done"):
                    break


def embed(text: str, model: Optional[str] = None) -> list[float]:
    """Get embeddings from Ollama."""
    if model is None:
        model = _cfg.get("models", {}).get("embed_model", "nomic-embed-text")

    resp = httpx.post(
        f"{_base_url()}/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


def coder_chat(messages: list[dict], **kwargs) -> str:
    """Use the coder model specifically."""
    model = _cfg.get("models", {}).get("coder_model", "qwen2.5-coder:7b")
    return chat(messages, model=model, temperature=0.2, **kwargs)


def whisper(prompt: str) -> str:
    """Generate a one-line ghostly whisper."""
    model = _cfg.get("models", {}).get("persona_model", "llama3.1:8b")
    return chat(
        [{"role": "user", "content": prompt}],
        model=model,
        temperature=1.1,
    ).strip()


def check_ollama() -> bool:
    """Return True if Ollama is reachable."""
    try:
        r = httpx.get(f"{_base_url()}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    """List available models from Ollama."""
    try:
        r = httpx.get(f"{_base_url()}/api/tags", timeout=5)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []
