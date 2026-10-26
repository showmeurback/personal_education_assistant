"""SimHash — отпечаток текста для обнаружения почти-дубликатов (Charikar, 2002).

Текст представляется множеством шинглов — последовательностей из k лемм.
Каждый шингл хешируется в b-битное число; для каждого бита суммируются веса
шинглов (+w, если бит равен 1, иначе −w). Итоговый бит отпечатка равен 1,
если сумма положительна. Близкие тексты дают отпечатки с малым расстоянием
Хэмминга, что позволяет искать заимствования без языковой модели.
"""
from __future__ import annotations

import hashlib
from collections import Counter


def shingles(tokens: list[str], k: int = 3) -> Counter:
    if len(tokens) < k:
        return Counter([" ".join(tokens)]) if tokens else Counter()
    return Counter(" ".join(tokens[i:i + k]) for i in range(len(tokens) - k + 1))


def _hash(feature: str, bits: int) -> int:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=bits // 8).digest()
    return int.from_bytes(digest, "big")


def simhash_bits(tokens: list[str], bits: int = 64, k: int = 3) -> list[int]:
    """Возвращает отпечаток в виде списка из `bits` нулей и единиц."""
    weights = [0] * bits
    features = shingles(tokens, k)
    if not features:
        return [0] * bits
    for feature, weight in features.items():
        h = _hash(feature, bits)
        for i in range(bits):
            if (h >> i) & 1:
                weights[i] += weight
            else:
                weights[i] -= weight
    return [1 if w > 0 else 0 for w in weights]


def hamming(a: list[int], b: list[int]) -> int:
    return sum(x != y for x, y in zip(a, b))


def similarity(a: list[int], b: list[int]) -> float:
    """Доля совпадающих бит отпечатков: 1.0 — идентичные тексты."""
    return 1.0 - hamming(a, b) / max(1, len(a))


# совместимость с прежним интерфейсом модуля
def create_simhash_vector(text: str) -> list[int]:
    from .normalizer import TextNormalizer
    return simhash_bits(TextNormalizer().lemmas(text))
