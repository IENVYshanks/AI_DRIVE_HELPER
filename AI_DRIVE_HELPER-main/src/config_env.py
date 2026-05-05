from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache
def get_env_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".env"


def load_env_file() -> None:
    env_path = get_env_path()
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_env(name: str, default: str | None = None) -> str | None:
    load_env_file()
    value = os.environ.get(name)
    if value not in (None, ""):
        return value
    return default
