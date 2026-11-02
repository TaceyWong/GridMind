from __future__ import annotations

from pathlib import Path


def load_text_file(path: Path) -> tuple[str, dict]:
    text = path.read_text(encoding="utf-8")
    meta = {"source": path.name, "path": str(path)}
    return text, meta


def load_directory(directory: Path, patterns: tuple[str, ...] = ("*.md", "*.txt")) -> list[tuple[str, dict]]:
    docs: list[tuple[str, dict]] = []
    if not directory.exists():
        return docs
    for pattern in patterns:
        for path in sorted(directory.glob(pattern)):
            docs.append(load_text_file(path))
    return docs
