"""Deterministic stand-in for sentence-transformers.

Tests never load the real MiniLM model (slow, large download). Texts that share
words get similar vectors, so retrieval behaves sensibly in tests.
"""

import hashlib

import numpy as np

DIM = 384


def _vector(text: str) -> np.ndarray:
    vec = np.zeros(DIM, dtype=np.float32)
    for word in text.lower().split():
        word = word.strip(".,!?;:\"'()[]")
        if not word:
            continue
        idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM
        vec[idx] += 1.0
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


class FakeSentenceTransformer:
    def __init__(self, *_args, **_kwargs):
        pass

    def encode(self, texts, **_kwargs):
        if isinstance(texts, str):
            return _vector(texts)
        return np.stack([_vector(t) for t in texts])
