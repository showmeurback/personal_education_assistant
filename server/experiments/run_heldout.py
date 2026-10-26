"""Проверка на отложенном наборе реальных отчётов (не использовался при настройке).

Набор (real/heldout_reports.json): 17 реальных отчётов по двум дисциплинам, сданных и
принятых преподавателями, с рисунками. Проверки:
  real_ok          — отчёт по своей лабораторной работе (ожидается «принять»);
  wrong_course     — тот же отчёт, приложенный к лабораторной другой дисциплины («отклонить»);
  wrong_lab        — тот же отчёт, приложенный к другой лабораторной той же дисциплины
                     («отклонить»; пары подобраны так, чтобы темы не совпадали).
Требования к отчёту: не менее 100 слов, разделы «Цель» и «Вывод|Заключение».

Конфигурация задаётся переменными окружения, метка — аргументом --tag:
  v2: LLM_JUDGE_MODELS=same VISION_ENABLED=false   (одна модель, без рисунков)
  v3: настройки по умолчанию                        (своя модель у каждого оценщика, описание рисунков)

Запуск (из server/):  LLM_JUDGE_MODELS=same VISION_ENABLED=false python experiments/run_heldout.py --tag v2
                       python experiments/run_heldout.py --tag v3
Результаты: experiments/results/heldout_<tag>_{raw,summary}.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "src"))
sys.path.insert(0, str(ROOT))

from agents.verification import judges  # noqa: E402
from agents.verification.pipeline import VerificationPipeline  # noqa: E402
from agents.verification.rules import LabRequirements  # noqa: E402
from common.documents import ReportImage  # noqa: E402
from database.vector.repositories.report_index import InMemoryReportIndex  # noqa: E402
from run_experiment import agreement, by_category, metrics  # noqa: E402
from settings import llm_settings, vision_settings  # noqa: E402

RESULTS = ROOT / "results"
REAL = ROOT / "real"
SECTIONS = ["Цель", "Вывод|Заключение"]
MIN_WORDS = 100
JUDGES = ("strict", "objective", "loyal")


def load(dataset: str) -> list[dict]:
    if dataset == "dev":  # набор, на котором система настраивалась (без рисунков)
        reports = json.loads((REAL / "real_reports.json").read_text(encoding="utf-8"))
        for r in reports:
            r["images"] = []
        return reports
    return json.loads((REAL / "heldout_reports.json").read_text(encoding="utf-8"))


def build_items(reports: list[dict], within_shift: int = 4) -> tuple[list[dict], dict[int, LabRequirements]]:
    # задания других работ той же дисциплины — для правила R7 (к какой работе курса отчёт ближе)
    labs = {101 + i: LabRequirements(task=r["task"], min_words=MIN_WORDS, required_sections=SECTIONS,
                                     other_tasks=[x["task"] for j, x in enumerate(reports)
                                                  if j != i and x["course"] == r["course"]])
            for i, r in enumerate(reports)}
    by_course: dict[str, list[int]] = {}
    for i, r in enumerate(reports):
        by_course.setdefault(r["course"], []).append(i)
    courses = list(by_course)
    items = []

    def add(i: int, j: int, category: str, expected: str, student: int) -> None:
        r = reports[i]
        title = r["title"] if i == j else f"{r['title']} → {reports[j]['course']} {reports[j]['title']}"
        items.append({"id": len(items) + 1, "lab": 101 + j, "student": student, "category": category,
                      "expected": expected, "course": r["course"], "title": title, "report": i})

    for i in range(len(reports)):
        add(i, i, "real_ok", "approve", 2000 + i)
    if len(courses) > 1:
        for i, r in enumerate(reports):
            own = by_course[r["course"]]
            other = by_course[courses[(courses.index(r["course"]) + 1) % len(courses)]]
            add(i, other[own.index(i) % len(other)], "wrong_course", "reject", 3000 + i)
    for i, r in enumerate(reports):
        own = by_course[r["course"]]
        if len(own) > within_shift:
            add(i, own[(own.index(i) + within_shift) % len(own)], "wrong_lab", "reject", 4000 + i)
    return items, labs


def images_of(report: dict) -> list[ReportImage]:
    out = []
    for n, name in enumerate(report.get("images", []), start=1):
        out.append(ReportImage(n, (REAL / "heldout_images" / name).read_bytes(), name))
    return out


async def run_mode(mode: str, items: list[dict], labs: dict[int, LabRequirements],
                   reports: list[dict]) -> list[dict]:
    index = InMemoryReportIndex()
    pipeline = VerificationPipeline(index, mode=mode)
    rows = []
    for n, it in enumerate(items, start=1):
        report = reports[it["report"]]
        t0 = time.perf_counter()
        res = await pipeline.run(text=report["text"], images=images_of(report), requirements=labs[it["lab"]],
                                 student_id=it["student"], lab_id=it["lab"])
        wall = time.perf_counter() - t0
        if res.fingerprint and res.decided_by not in ("simhash", "rules"):
            index.add(res.fingerprint, report_id=it["id"], student_id=it["student"], lab_id=it["lab"])
        img_step = next((s for s in res.protocol if s["title"] == "Описание изображений"), None)
        agg_step = next((s for s in res.protocol if s["title"] == "Агрегация вердиктов"), None)
        r7_step = next((s for s in res.protocol if s["title"].startswith("Соответствие лабораторной")), None)
        rows.append({
            "mode": mode, "repeat": 1, "id": it["id"], "lab": it["lab"], "category": it["category"],
            "expected": it["expected"], "course": it["course"], "title": it["title"],
            "decision": res.decision.value, "decided_by": res.decided_by, "score": res.score,
            "llm_calls": res.llm_calls, "vision_calls": res.vision_calls, "seconds": round(wall, 2),
            "image_seconds": round(img_step["duration_ms"] / 1000, 2) if img_step else 0.0,
            "images_described": img_step["details"]["described"] if img_step else 0,
            "reason": res.reason,
            "rule": agg_step["details"].get("rule") if agg_step else None,
            "lab_match": r7_step["details"]["lab_match"] if r7_step else None,
            "judges": [{"judge": v["judge"], "model": v.get("model"), "valid": v["valid"], "verdict": v["verdict"],
                        "confidence": v["confidence"], "summary": v["summary"], "error": v["error"],
                        "seconds": round(v["duration_ms"] / 1000, 1)} for v in res.verdicts]})
        print(f"[{mode}] {n}/{len(items)} id={it['id']} {it['category']:<12} → {res.decision.value:<13} "
              f"({res.decided_by}) {wall:.1f}s img={rows[-1]['image_seconds']}s "
              f"{[(j['judge'][0], j['verdict'], j['seconds']) for j in rows[-1]['judges']]}", flush=True)
    return rows


def judge_stats(rows: list[dict]) -> dict:
    """Точность каждого оценщика в отдельности и попарная согласованность ошибок."""
    out = {}
    for j in JUDGES:
        vs = [(r, next((x for x in r["judges"] if x["judge"] == j), None)) for r in rows]
        vs = [(r, x) for r, x in vs if x and x["valid"]]
        ok = sum(1 for r, x in vs if x["verdict"] == (r["expected"] == "approve"))
        out[j] = {"model": vs[0][1]["model"] if vs else None, "valid": len(vs),
                  "accuracy": round(ok / len(vs), 3) if vs else None,
                  "seconds_median": statistics.median(x["seconds"] for _, x in vs) if vs else None}
    errors = {j: {r["id"] for r in rows for x in r["judges"] if x["judge"] == j and x["valid"]
                  and x["verdict"] != (r["expected"] == "approve")} for j in JUDGES}
    out["shared_errors"] = {f"{a}+{b}": len(errors[a] & errors[b])
                            for i, a in enumerate(JUDGES) for b in JUDGES[i + 1:]}
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--dataset", default="heldout", choices=["heldout", "dev"])
    ap.add_argument("--modes", default="symbolic,hybrid,neural")
    args = ap.parse_args()
    reports = load(args.dataset)
    items, labs = build_items(reports, within_shift=4 if args.dataset == "heldout" else 2)
    RESULTS.mkdir(exist_ok=True)
    name = f"{args.dataset}_{args.tag}"
    # гибридный вариант идёт первым и измеряет время честно; нейросетевой переиспользует
    # оценки ансамбля для одинаковых входов без воспроизведения времени ответа
    judges.enable_cache(replay_delay=False)
    raw: list[dict] = []
    started = time.time()
    modes = args.modes.split(",")
    for mode in modes:
        raw.extend(await run_mode(mode, items, labs, reports))
        (RESULTS / f"{name}_raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    judges.disable_cache()
    summary = {
        "tag": args.tag, "dataset": args.dataset, "checks": len(items), "reports": len(reports),
        "judge_models": {j: llm_settings.model_for_judge(j) for j in JUDGES},
        "vision": {"enabled": vision_settings.enabled, "model": vision_settings.model,
                   "max_images": vision_settings.max_images},
        "duration_minutes": round((time.time() - started) / 60, 1), "modes": {},
    }
    for mode in modes:
        rows = [r for r in raw if r["mode"] == mode]
        m = metrics(rows)
        secs = [r["seconds"] for r in rows]
        m.update({"seconds_median": round(statistics.median(secs), 1), "seconds_max": round(max(secs), 1),
                  "image_seconds_median": round(statistics.median(r["image_seconds"] for r in rows), 1),
                  "vision_calls_total": sum(r["vision_calls"] for r in rows)})
        summary["modes"][mode] = {"metrics": m, "by_category": by_category(rows)}
        if mode != "symbolic":
            summary["modes"][mode]["judges"] = judge_stats(rows)
    if "neural" in modes and "hybrid" in modes:
        summary["agreement_neural_hybrid"] = agreement([r for r in raw if r["mode"] == "neural"],
                                                       [r for r in raw if r["mode"] == "hybrid"])
    (RESULTS / f"{name}_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                                  encoding="utf-8")
    print(json.dumps({m: v["metrics"] for m, v in summary["modes"].items()}, ensure_ascii=False, indent=1))
    for m, v in summary["modes"].items():
        print(m, v["by_category"], v.get("judges"))


if __name__ == "__main__":
    asyncio.run(main())
