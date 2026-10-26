"""Сравнительный эксперимент: символьный, нейросетевой и гибридный варианты проверки отчётов.

Каждый вариант прогоняется по одному и тому же размеченному набору (dataset.json)
с отдельным индексом отпечатков в памяти. Порядок отчётов фиксирован: исходные
отчёты обрабатываются раньше копий, как это происходит при реальной сдаче.

Запуск (из server/, нужен ключ API в окружении):
    python experiments/run_experiment.py --repeats 2
Результаты: experiments/results/{raw.json, summary.json, summary.md}
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "src"))
sys.path.insert(0, str(ROOT))

from agents.verification import judges  # noqa: E402
from agents.verification.pipeline import VerificationPipeline  # noqa: E402
from agents.verification.rules import LabRequirements  # noqa: E402
from database.vector.repositories.report_index import InMemoryReportIndex  # noqa: E402
from labs import LABS  # noqa: E402
from settings import llm_settings  # noqa: E402

RESULTS = ROOT / "results"


async def run_mode(mode: str, items: list[dict], repeat: int) -> list[dict]:
    index = InMemoryReportIndex()
    pipeline = VerificationPipeline(index, mode=mode)
    rows = []
    for n, it in enumerate(items, start=1):
        lab = LABS[it["lab"]]
        req = LabRequirements(task=lab["task"], min_words=lab["min_words"],
                              required_sections=lab["required_sections"],
                              # три лабораторные набора рассматриваются как работы одного курса (правило R7)
                              other_tasks=[x["task"] for k, x in LABS.items() if k != it["lab"]])
        t0 = time.perf_counter()
        res = await pipeline.run(text=it["text"], requirements=req, student_id=it["student"], lab_id=it["lab"])
        wall = time.perf_counter() - t0
        if res.fingerprint and res.decided_by not in ("simhash", "rules"):
            index.add(res.fingerprint, report_id=it["id"], student_id=it["student"], lab_id=it["lab"])
        rows.append({
            "mode": mode, "repeat": repeat, "id": it["id"], "lab": it["lab"], "category": it["category"],
            "expected": it["expected"], "decision": res.decision.value, "decided_by": res.decided_by,
            "score": res.score, "similarity": res.max_similarity, "llm_calls": res.llm_calls,
            "seconds": round(wall, 2), "reason": res.reason,
            "rule": next((st["details"].get("rule") for st in res.protocol
                          if st["title"] == "Агрегация вердиктов"), None),
            "lab_doubt": next((st["details"]["lab_match"]["doubt"] for st in res.protocol
                               if st["title"].startswith("Соответствие лабораторной")), None),
            "judges": [{"judge": v["judge"], "model": v.get("model"), "valid": v["valid"], "verdict": v["verdict"],
                        "confidence": v["confidence"], "error": v["error"]} for v in res.verdicts],
        })
        print(f"[{mode} #{repeat}] {n}/{len(items)} id={it['id']} {it['category']:<11} → "
              f"{res.decision.value:<13} ({res.decided_by}) {wall:.1f}s", flush=True)
    return rows


def metrics(rows: list[dict]) -> dict:
    total = len(rows)
    good = [r for r in rows if r["expected"] == "approve"]
    bad = [r for r in rows if r["expected"] == "reject"]
    auto = [r for r in rows if r["decision"] != "manual_review"]
    correct_auto = [r for r in auto if r["decision"] == r["expected"]]
    false_accept = [r for r in bad if r["decision"] == "approve"]
    false_reject = [r for r in good if r["decision"] == "reject"]
    manual = [r for r in rows if r["decision"] == "manual_review"]
    # итоговая точность «система + преподаватель»: ручная проверка считается верным исходом
    resolved = len(correct_auto) + len(manual)
    tp = sum(1 for r in bad if r["decision"] == "reject")  # «положительный класс» — неприемлемый отчёт
    fp = sum(1 for r in good if r["decision"] == "reject")
    fn = sum(1 for r in bad if r["decision"] == "approve")
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "reports": total,
        "accuracy_auto": round(len(correct_auto) / len(auto), 3) if auto else None,
        "coverage": round(len(auto) / total, 3),
        "accuracy_strict": round(len(correct_auto) / total, 3),
        "accuracy_with_teacher": round(resolved / total, 3),
        "precision_reject": round(precision, 3),
        "recall_reject": round(recall, 3),
        "f1_reject": round(2 * precision * recall / (precision + recall), 3) if precision + recall else 0.0,
        "false_accept_rate": round(len(false_accept) / len(bad), 3) if bad else None,
        "false_reject_rate": round(len(false_reject) / len(good), 3) if good else None,
        "manual_rate": round(len(manual) / total, 3),
        "llm_calls_total": sum(r["llm_calls"] for r in rows),
        "llm_calls_mean": round(statistics.mean(r["llm_calls"] for r in rows), 2),
        "seconds_mean": round(statistics.mean(r["seconds"] for r in rows), 2),
        "seconds_median": round(statistics.median(r["seconds"] for r in rows), 2),
        "decided_by": dict(Counter(r["decided_by"] for r in rows)),
        "invalid_judgements": sum(1 for r in rows for j in r["judges"] if not j["valid"]),
    }


def by_category(rows: list[dict]) -> dict:
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        out[r["category"]][r["decision"]] += 1
    return {k: dict(v) for k, v in out.items()}


def agreement(a: list[dict], b: list[dict]) -> float:
    da = {r["id"]: r["decision"] for r in a}
    same = sum(1 for r in b if da.get(r["id"]) == r["decision"])
    return round(same / len(b), 3) if b else 0.0


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(ROOT / "dataset.json"))
    ap.add_argument("--modes", default="symbolic,neural,hybrid")  # neural до hybrid: кэш оценок
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-replay", action="store_true",
                    help="не воспроизводить время ответа при повторном использовании оценок (время гибридного варианта не измеряется)")
    ap.add_argument("--resume", action="store_true",
                    help="дописать недостающие прогоны (режим, повтор) к имеющемуся raw.json")
    ap.add_argument("--rescore", action="store_true",
                    help="пересчитать сводку по raw.json с текущими метками набора (без обращений к модели)")
    ap.add_argument("--no-share", action="store_true",
                    help="не переиспользовать оценки ансамбля между нейросетевым и гибридным вариантами")
    args = ap.parse_args()

    items = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    if args.rescore:
        labels = {it["id"]: it["expected"] for it in items}
        raw = json.loads((RESULTS / "raw.json").read_text(encoding="utf-8"))
        for r in raw:
            r["expected"] = labels[r["id"]]
        prev = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
        summary = {k: prev[k] for k in ("model", "provider", "dataset_size", "categories", "duration_minutes",
                                         "shared_judgements") if k in prev}
        summary["relabeled"] = [it["id"] for it in items if it.get("note")]
        summary["modes"] = {}
        for mode in [m for m in ("symbolic", "neural", "hybrid") if any(r["mode"] == m for r in raw)]:
            rows = [r for r in raw if r["mode"] == mode]
            first = [r for r in rows if r["repeat"] == 1]
            entry = {"metrics": metrics(first), "by_category": by_category(first)}
            reps = sorted({r["repeat"] for r in rows})
            if len(reps) > 1:
                second = [r for r in rows if r["repeat"] == reps[1]]
                entry["reproducibility"] = agreement(first, second)
                entry["metrics_repeat2"] = metrics(second)
            summary["modes"][mode] = entry
        (RESULTS / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
        (RESULTS / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        write_markdown(summary)
        print(json.dumps({m: v["metrics"] for m, v in summary["modes"].items()}, ensure_ascii=False, indent=1))
        return
    items = [it for it in items if it.get("expected") in ("approve", "reject")]
    if args.limit:
        items = items[:args.limit]
    RESULTS.mkdir(exist_ok=True)
    raw: list[dict] = []
    if args.resume and (RESULTS / "raw.json").exists():
        raw = json.loads((RESULTS / "raw.json").read_text(encoding="utf-8"))
    done = {(r["mode"], r["repeat"]) for r in raw if True}
    started = time.time()
    modes = args.modes.split(",")
    # Повтор r нейросетевого и гибридного вариантов использует одни и те же оценки ансамбля
    # (входы оценщиков идентичны), а разные повторы — независимые обращения к модели.
    for rep in range(1, args.repeats + 1):
        if not args.no_share:
            judges.enable_cache(replay_delay=not args.no_replay)
        for mode in modes:
            if mode == "symbolic" and rep > 1:
                continue  # символьный вариант детерминирован
            if (mode, rep) in done and sum(1 for r in raw if (r["mode"], r["repeat"]) == (mode, rep)) == len(items):
                continue  # прогон уже выполнен (--resume)
            raw.extend(await run_mode(mode, items, rep))
            (RESULTS / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    judges.disable_cache()

    summary = {"model": {j: llm_settings.model_for_judge(j) for j in ("strict", "objective", "loyal")},
               "provider": llm_settings.base_url,
               "dataset_size": len(items), "categories": dict(Counter(i["category"] for i in items)),
               "duration_minutes": round((time.time() - started) / 60, 1), "modes": {}}
    summary["shared_judgements"] = not args.no_share
    for mode in modes:
        rows = [r for r in raw if r["mode"] == mode]
        first = [r for r in rows if r["repeat"] == 1]
        entry = {"metrics": metrics(first), "by_category": by_category(first)}
        repeats = sorted({r["repeat"] for r in rows})
        if len(repeats) > 1:
            second = [r for r in rows if r["repeat"] == repeats[1]]
            entry["reproducibility"] = agreement(first, second)
            entry["metrics_repeat2"] = metrics(second)
        summary["modes"][mode] = entry
    (RESULTS / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(summary)
    print(json.dumps({m: v["metrics"] for m, v in summary["modes"].items()}, ensure_ascii=False, indent=1))


def write_markdown(summary: dict) -> None:
    keys = ["accuracy_auto", "coverage", "accuracy_strict", "accuracy_with_teacher", "precision_reject",
            "recall_reject", "f1_reject", "false_accept_rate", "false_reject_rate", "manual_rate",
            "llm_calls_mean", "seconds_mean"]
    modes = list(summary["modes"])
    lines = [f"Модель: {summary['model']}; отчётов: {summary['dataset_size']}", "",
             "| Метрика | " + " | ".join(modes) + " |", "|---|" + "---|" * len(modes)]
    for k in keys:
        lines.append(f"| {k} | " + " | ".join(str(summary["modes"][m]["metrics"].get(k)) for m in modes) + " |")
    lines.append("")
    for m in modes:
        if "reproducibility" in summary["modes"][m]:
            lines.append(f"Воспроизводимость решений ({m}): {summary['modes'][m]['reproducibility']}")
    (RESULTS / "summary.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
