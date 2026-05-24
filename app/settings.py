import os
from pathlib import Path


def _normalize_secret(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def get_secret(name: str) -> str:
    value = _normalize_secret(os.getenv(name, ""))
    if value:
        return value

    file_path = _normalize_secret(os.getenv(f"{name}_FILE", ""))
    if file_path:
        secret_value = _normalize_secret(Path(file_path).read_text(encoding="utf-8"))
        if secret_value:
            return secret_value

    raise RuntimeError(f"{name} or {name}_FILE is required")
