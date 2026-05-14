import re
from pathlib import Path

SAFE_NAME_PATTERN = re.compile(r"[^a-zA-Z0-9._-]+")


def sanitize_filename(value: str) -> str:
    sanitized = SAFE_NAME_PATTERN.sub("_", value).strip("._")
    return sanitized or "artifact"


def safe_join(root: Path, *parts: str) -> Path:
    candidate = root.joinpath(*parts).resolve()
    root_resolved = root.resolve()
    if root_resolved not in candidate.parents and candidate != root_resolved:
        raise ValueError("Обнаружена попытка выхода за пределы разрешённого каталога")
    return candidate

