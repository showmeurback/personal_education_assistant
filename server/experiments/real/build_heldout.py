"""Отложенный набор реальных отчётов (не использовался при настройке системы).

Вход: каталог с исходными .docx (в репозиторий не входят).
Выход: real/heldout_reports.json (обезличенный текст с маркерами рисунков ⟦img:N⟧)
       и real/heldout_images/<sha>.jpg (рисунки, уменьшенные до 1024 пикселей).

Обезличивание: титульный лист (всё до строки «Минск <год>») удаляется,
оставшиеся упоминания фамилий заменяются на «Студент».
Задание лабораторной берётся из начала отчёта: от «Цели» до начала
изложения решения («Решение», «Ход работы», «Демонстрация» и т. п.).

Запуск (из server/):  python experiments/real/build_heldout.py <каталог с docx>
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from common.documents import MARKER, MARKER_RE, extract_document, strip_markers  # noqa: E402

# ключ файла → (дисциплина, название лабораторной)
REPORTS = {
    "1bfc89e7": ("ГИИС", "ЛР 1. Построение отрезков"),
    "b35e1637": ("ГИИС", "ЛР 2. Построение линий второго порядка"),
    "c0d9f77f": ("ГИИС", "ЛР 3. Построение параметрических кривых"),
    "04306cf0": ("ГИИС", "ЛР 4. Геометрические преобразования 3D-объектов"),
    "bc019728": ("ГИИС", "ЛР 5. Обработка полигонов, выпуклые оболочки"),
    "496b5005": ("ГИИС", "ЛР 6. Заполнение полигонов"),
    "7625d4bd": ("ГИИС", "ЛР 7. Триангуляция Делоне и диаграмма Вороного"),
    "192014ae": ("ГИИС", "ЛР 8. Удаление невидимых линий и граней"),
    "1b7c9ab7": ("ЕЯзИИС", "ЛР 1. Система формирования словаря"),
    "55cfc2a2": ("ЕЯзИИС", "ЛР 2. Корпус текстов и корпусный менеджер"),
    "08e58fce": ("ЕЯзИИС", "ЛР 3. Синтаксический анализ текстов"),
    "6c4ceef0": ("ЕЯзИИС", "ЛР 4. Семантико-синтаксический анализ"),
    "d21498d0": ("ЕЯзИИС", "ЛР 4. Автоматический машинный перевод"),
    "740adcbc": ("ЕЯзИИС", "ЛР 5. Диалоговая система (проектирование)"),
    "ece4e027": ("ЕЯзИИС", "ЛР 6. Диалоговая система (разработка)"),
    "8849410b": ("ЕЯзИИС", "ЛР 5–7. Закономерности речевого сигнала"),
    "84681217": ("ЕЯзИИС", "ЛР 8. Система синтеза речи"),
}
NAMES = re.compile(r"\b(Ка[кд]?диков|Агеенко|Забков|Сальников|Крапивин)\w*(\s+[А-ЯЁ]\.\s?[А-ЯЁ]?\.?)?")
SOLUTION = re.compile(r"^\s*(\d+[.)]?\s*)?(Решение|Ход (выполнения )?работы|Ход выполнения|Демонстрация|"
                      r"Выполнение работы|Результаты работы|Практическая часть|Реализация|Описание программы|"
                      r"Используем(ые библиотеки|ое программное)|Интерфейс$|Структура разработанной|Для реализации)",
                      re.IGNORECASE)
MAX_TASK = 1500


def anonymize(text: str) -> str:
    lines = text.split("\n")
    cut = next((i for i, l in enumerate(lines[:40]) if re.match(r"^\s*Минск\s+\d{4}", l)), -1)
    return NAMES.sub("Студент", "\n".join(lines[cut + 1:])).strip()


def task_of(text: str) -> str:
    out = []
    for line in strip_markers(text).split("\n"):
        if out and SOLUTION.match(line):
            break
        out.append(line)
    return "\n".join(out)[:MAX_TASK].strip()


def main(src: Path) -> None:
    from PIL import Image

    img_dir = HERE / "heldout_images"
    img_dir.mkdir(exist_ok=True)
    reports = []
    for key, (course, title) in REPORTS.items():
        path = next(src.glob(f"{key}-*.docx"))
        doc = extract_document(path.read_bytes(), path.name)
        text = anonymize(doc.text)
        kept = {int(m) for m in MARKER_RE.findall(text)}
        images, renum = [], {}
        for img in doc.images:
            if img.index not in kept:
                continue
            try:
                im = Image.open(io.BytesIO(img.data))
                im.load()
            except Exception:
                continue
            if im.mode not in ("RGB", "L"):
                bg = Image.new("RGB", im.size, "white")
                rgba = im.convert("RGBA")
                bg.paste(rgba, mask=rgba.split()[-1])
                im = bg
            im.thumbnail((1024, 1024))
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "JPEG", quality=82)
            name = f"{img.sha256[:16]}.jpg"
            (img_dir / name).write_bytes(buf.getvalue())
            renum[img.index] = len(images) + 1
            images.append(name)
        text = MARKER_RE.sub(lambda m: f" {MARKER.format(renum[int(m.group(1))])} "
                             if int(m.group(1)) in renum else " ", text)
        reports.append({"key": key, "course": course, "title": title, "task": task_of(text),
                        "text": text, "images": images})
        print(f"{key} {course:7} {title[:45]:45} слов {len(strip_markers(text).split()):5} "
              f"рисунков {len(images):3} задание {len(reports[-1]['task'])}")
    (HERE / "heldout_reports.json").write_text(json.dumps(reports, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
