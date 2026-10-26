"""Эксперимент на реальных отчётах студента (обезличенных).

Набор: 10 реальных отчётов по трём дисциплинам, сданных и принятых преподавателями
(ожидаемое решение — «принять»), и 10 «ошибочно приложенных» отчётов: тот же реальный
отчёт, сданный по лабораторной работе другой дисциплины (ожидаемое решение — «отклонить»).
Задание каждой лабораторной работы взято из соответствующего отчёта (раздел «Цель»
и «Задание»/«Требования»), требования к отчёту: не менее 100 слов, разделы «Цель» и
«Вывод|Заключение».

Запуск (из server/):  python experiments/run_real.py
Результаты: experiments/results/{real_raw.json, real_summary.json}
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "src"))
sys.path.insert(0, str(ROOT))

from agents.verification import judges  # noqa: E402
from agents.verification.normalizer import TextNormalizer  # noqa: E402
from agents.verification.pipeline import VerificationPipeline  # noqa: E402
from agents.verification.rules import LabRequirements, apply_rules, build_facts, Outcome  # noqa: E402
from database.vector.repositories.report_index import InMemoryReportIndex  # noqa: E402
from run_experiment import agreement, by_category, metrics  # noqa: E402
from settings import llm_settings  # noqa: E402

RESULTS = ROOT / "results"
SECTIONS = ["Цель", "Вывод|Заключение"]
MIN_WORDS = 100


def build_items() -> tuple[list[dict], dict[int, LabRequirements]]:
    reports = json.loads((ROOT / "real" / "real_reports.json").read_text(encoding="utf-8"))
    labs = {101 + i: LabRequirements(task=r["task"], min_words=MIN_WORDS, required_sections=SECTIONS)
            for i, r in enumerate(reports)}
    items = []
    for i, r in enumerate(reports):
        items.append({"id": 1 + i, "lab": 101 + i, "student": 2000 + i, "category": "real_ok",
                      "expected": "approve", "course": r["course"], "title": r["title"], "text": r["text"]})
    n = len(reports)
    for i, r in enumerate(reports):
        j = (i + 4) % n  # лабораторная работа другой дисциплины
        assert reports[j]["course"] != r["course"]
        items.append({"id": 1 + n + i, "lab": 101 + j, "student": 3000 + i, "category": "real_wrong_lab",
                      "expected": "reject", "course": r["course"], "title": f"{r['title']} → {reports[j]['title']}",
                      "text": r["text"]})
    return items, labs


def strict_r3_baseline(items: list[dict], labs: dict[int, LabRequirements]) -> int:
    """Сколько принятых отчётов отклонила бы исходная настройка R3 («Цель», «Вывод»)."""
    norm = TextNormalizer()
    blocked = 0
    for it in items:
        if it["category"] != "real_ok":
            continue
        req = LabRequirements(task=labs[it["lab"]].task, min_words=MIN_WORDS, required_sections=["Цель", "Вывод"])
        res = apply_rules(build_facts(it["text"], norm.lemmas(it["text"]), norm.lemmas(req.task)), req)
        blocked += any(r.outcome is Outcome.BLOCK for r in res)
    return blocked


async def run_mode(mode: str, items: list[dict], labs: dict[int, LabRequirements]) -> list[dict]:
    index = InMemoryReportIndex()
    pipeline = VerificationPipeline(index, mode=mode)
    rows = []
    for n, it in enumerate(items, start=1):
        t0 = time.perf_counter()
        res = await pipeline.run(text=it["text"], requirements=labs[it["lab"]], student_id=it["student"],
                                 lab_id=it["lab"])
        wall = time.perf_counter() - t0
        if res.fingerprint and res.decided_by not in ("simhash", "rules"):
            index.add(res.fingerprint, report_id=it["id"], student_id=it["student"], lab_id=it["lab"])
        rows.append({"mode": mode, "repeat": 1, "id": it["id"], "lab": it["lab"], "category": it["category"],
                     "expected": it["expected"], "title": it["title"], "decision": res.decision.value,
                     "decided_by": res.decided_by, "score": res.score, "similarity": res.max_similarity,
                     "llm_calls": res.llm_calls, "seconds": round(wall, 2), "reason": res.reason,
                     "rules": [s["details"].get("rules") for s in res.protocol if s["title"] == "Продукционные правила"],
                     "judges": [{"judge": v["judge"], "valid": v["valid"], "verdict": v["verdict"],
                                 "confidence": v["confidence"], "summary": v["summary"], "error": v["error"]}
                                for v in res.verdicts]})
        print(f"[{mode}] {n}/{len(items)} id={it['id']} {it['category']:<15} → {res.decision.value:<13} "
              f"({res.decided_by}) {wall:.1f}s", flush=True)
    return rows


async def main() -> None:
    items, labs = build_items()
    RESULTS.mkdir(exist_ok=True)
    judges.enable_cache()  # нейросетевой и гибридный варианты используют одни и те же оценки
    raw: list[dict] = []
    started = time.time()
    for mode in ("symbolic", "neural", "hybrid"):
        raw.extend(await run_mode(mode, items, labs))
        (RESULTS / "real_raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    judges.disable_cache()
    summary = {"model": llm_settings.judge_model or llm_settings.model, "reports": len(items),
               "strict_r3_blocked_accepted": strict_r3_baseline(items, labs),
               "duration_minutes": round((time.time() - started) / 60, 1), "modes": {}}
    for mode in ("symbolic", "neural", "hybrid"):
        rows = [r for r in raw if r["mode"] == mode]
        summary["modes"][mode] = {"metrics": metrics(rows), "by_category": by_category(rows)}
    summary["agreement_neural_hybrid"] = agreement([r for r in raw if r["mode"] == "neural"],
                                                   [r for r in raw if r["mode"] == "hybrid"])
    (RESULTS / "real_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({m: v["metrics"] for m, v in summary["modes"].items()}, ensure_ascii=False, indent=1))
    print("strict R3 would block accepted:", summary["strict_r3_blocked_accepted"])


if __name__ == "__main__":
    asyncio.run(main())
