"""Нормализация текста: приведение к нижнему регистру, лемматизация (Natasha),
удаление стоп-слов. Результат — последовательность лемм, по которой строится
SimHash-отпечаток и проверяются продукционные правила."""
from __future__ import annotations

import re
import threading
from functools import lru_cache

from .stopwords import RUSSIAN_STOPWORDS

_CLEAN_RE = re.compile(r"[^a-zA-Zа-яёА-ЯЁ0-9\s-]")
_lock = threading.Lock()


class TextNormalizer:
    _instance = None

    def __new__(cls, *args, **kwargs):
        with _lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                from natasha import MorphVocab, NewsEmbedding, NewsMorphTagger, Segmenter
                inst._segmenter = Segmenter()
                inst._morph_vocab = MorphVocab()
                inst._morph_tagger = NewsMorphTagger(NewsEmbedding())
                cls._instance = inst
        return cls._instance

    def __init__(self, language: str = "russian") -> None:  # noqa: D401 — совместимость
        pass

    def lemmas(self, text: str, remove_stopwords: bool = True) -> list[str]:
        return list(_lemmas_cached(self, text, remove_stopwords))

    def normalize_text(self, text: str, remove_stopwords: bool = True) -> str:
        return " ".join(self.lemmas(text, remove_stopwords))

    def _lemmatize(self, text: str, remove_stopwords: bool) -> tuple[str, ...]:
        from natasha import Doc
        cleaned = _CLEAN_RE.sub(" ", text.lower())
        doc = Doc(cleaned)
        doc.segment(self._segmenter)
        doc.tag_morph(self._morph_tagger)
        out = []
        for token in doc.tokens:
            token.lemmatize(self._morph_vocab)
            lemma = (token.lemma or token.text).strip("-")
            if not lemma or lemma.isdigit():
                continue
            if remove_stopwords and lemma in RUSSIAN_STOPWORDS:
                continue
            out.append(lemma)
        return tuple(out)


@lru_cache(maxsize=256)
def _lemmas_cached(normalizer: TextNormalizer, text: str, remove_stopwords: bool) -> tuple[str, ...]:
    return normalizer._lemmatize(text, remove_stopwords)
