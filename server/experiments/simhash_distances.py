"""Распределение расстояний Хэмминга между отпечатками SimHash отчётов набора.

Пары берутся внутри одной лабораторной работы и делятся на три группы:
  copy_exact  — точная копия и её исходный отчёт;
  copy_light  — копия с мелкой правкой и её исходный отчёт;
  independent — любые два отчёта разных «авторов», не связанные копированием.
Результат: experiments/results/distances.json
Запуск (из server/):  python experiments/simhash_distances.py
"""
from __future__ import annotations

import json
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "src"))

from agents.verification.normalizer import TextNormalizer  # noqa: E402
from agents.verification.simhash import hamming, simhash_bits  # noqa: E402
from settings import verification_settings as cfg  # noqa: E402


def main() -> None:
    items = json.loads((ROOT / "dataset.json").read_text(encoding="utf-8"))
    norm = TextNormalizer()
    fp = {it["id"]: simhash_bits(norm.lemmas(it["text"]), bits=cfg.simhash_bits, k=cfg.simhash_shingle)
          for it in items}
    by_lab: dict[int, list[dict]] = {}
    for it in items:
        by_lab.setdefault(it["lab"], []).append(it)

    groups: dict[str, list[int]] = {"copy_exact": [], "copy_light": [], "independent": []}
    for lab_items in by_lab.values():
        originals = [it for it in lab_items if it["category"] == "original"]
        for it in lab_items:
            if it["category"] in ("copy_exact", "copy_light"):
                # источник копии — ближайший исходный отчёт той же работы
                groups[it["category"]].append(min(hamming(fp[it["id"]], fp[o["id"]]) for o in originals))
        derived = {"copy_exact", "copy_light", "too_short", "no_sections"}  # производные от оригиналов
        independent = [it for it in lab_items if it["category"] not in derived]
        for a, b in combinations(independent, 2):
            groups["independent"].append(hamming(fp[a["id"]], fp[b["id"]]))

    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    (out / "distances.json").write_text(json.dumps({"bits": cfg.simhash_bits,
                                                     "threshold": cfg.duplicate_max_hamming,
                                                     "groups": groups}, indent=1), encoding="utf-8")
    for k, v in groups.items():
        print(f"{k:<12} n={len(v):<4} min={min(v) if v else '-'} max={max(v) if v else '-'}")


if __name__ == "__main__":
    main()
