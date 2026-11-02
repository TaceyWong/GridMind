from __future__ import annotations

import hashlib
import math
import re


TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def hash_embed(text: str, dim: int = 64) -> list[float]:
    """Deterministic local embedding for offline demos (no API key required)."""
    vec = [0.0] * dim
    tokens = tokenize(text) or ["empty"]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(dim):
            vec[i] += ((digest[i % len(digest)] / 255.0) * 2 - 1) / len(tokens)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))
