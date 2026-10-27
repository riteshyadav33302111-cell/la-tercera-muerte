"""
Configuration loader. Reads config.toml from the project root or ~/.config/tercera/config.toml.
"""

from __future__ import annotations

import pathlib
from functools import lru_cache
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore

_DEFAULT_CONFIG: dict[str, Any] = {
    "ollama": {
        "base_url": "http://localhost:11434",
    },
    "models": {
        "persona_model": "llama3.1:8b",
        "coder_model": "qwen2.5-coder:7b",
        "embed_model": "nomic-embed-text",
    },
    "voice": {
        "enabled": False,
        "whisper_model": "base",
        "piper_voice": "en_US-lessac-medium",
        "reverb": True,
    },
    "seance": {
        "idle_whisper_seconds": 45,
        "typewriter_delay_ms": 30,
        "flicker_interval_ms": 200,
    },
    "sandbox": {
        "enabled": True,
        "timeout_seconds": 300,
    },
}


@lru_cache(maxsize=1)
def get_config() -> dict[str, Any]:
    """Load config, merging defaults with user config."""
    config = _deep_copy(_DEFAULT_CONFIG)

    candidates = [
        pathlib.Path.cwd() / "config.toml",
        pathlib.Path.home() / ".config" / "tercera" / "config.toml",
        pathlib.Path(__file__).parent.parent / "config.toml",
    ]

    for path in candidates:
        if path.exists() and tomllib is not None:
            with open(path, "rb") as f:
                user_cfg = tomllib.load(f)
            config = _deep_merge(config, user_cfg)
            break

    return config


def _deep_copy(d: dict) -> dict:
    import copy
    return copy.deepcopy(d)


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
