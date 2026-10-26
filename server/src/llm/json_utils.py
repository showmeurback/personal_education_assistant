"""Устойчивое извлечение JSON из ответа языковой модели.

Модели нередко оборачивают JSON в Markdown-блок, добавляют пояснения или
рассуждения (<think>…</think>). Функция находит первый корректный JSON-объект
или массив и возвращает его; при неудаче — None (решение о дальнейших действиях
принимает вызывающий символьный компонент).
"""
from __future__ import annotations

import json
import re
from typing import Any

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json(text: str) -> Any | None:
    if not text:
        return None
    cleaned = _THINK_RE.sub("", text).strip()

    candidates: list[str] = [m.group(1).strip() for m in _FENCE_RE.finditer(cleaned)]
    candidates.append(cleaned)

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            pass
        parsed = _scan_balanced(candidate)
        if parsed is not None:
            return parsed
    return None


def _scan_balanced(text: str) -> Any | None:
    """Ищет первую сбалансированную {...} или [...] подстроку, которая парсится как JSON."""
    for start, ch in enumerate(text):
        if ch not in "{[":
            continue
        closing = "}" if ch == "{" else "]"
        depth = 0
        in_str = False
        escape = False
        for end in range(start, len(text)):
            c = text[end]
            if in_str:
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == ch:
                depth += 1
            elif c == closing:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:end + 1])
                    except (json.JSONDecodeError, ValueError):
                        break
    return None
