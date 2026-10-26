import { useState } from "react";
import { Check, ChevronDown, CircleAlert, X, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProtocolStep, ReportCheck } from "@/api";
import { DECIDED_BY_MAP, DECISION_MAP } from "@/utils/constants";
import { Meter } from "@/components/common";

/**
 * Протокол гибридной проверки отчёта.
 * Символьные шаги изображаются квадратными узлами (кобальт), нейросетевые —
 * круглыми (фиолетовый); цвет кольца отражает результат шага.
 */
export function ProtocolView({ check, steps, teacher = false }: {
  check?: ReportCheck | null;
  steps: ProtocolStep[];
  teacher?: boolean;
}) {
  return (
    <div>
      {check && <DecisionSummary check={check} />}
      <ol className="relative mt-4">
        {steps.map((step, i) => (
          <StepRow key={step.step ?? i} step={step} last={i === steps.length - 1} teacher={teacher} />
        ))}
      </ol>
      <Legend />
    </div>
  );
}

function DecisionSummary({ check }: { check: ReportCheck }) {
  const d = DECISION_MAP[check.decision] ?? { label: check.decision, color: "" };
  return (
    <div className="grid grid-cols-2 gap-px rounded-md overflow-hidden border border-border bg-border">
      <SummaryCell label="Решение системы" value={<span className={d.color}>{d.label}</span>} />
      <SummaryCell label="Кем принято" value={DECIDED_BY_MAP[check.decided_by] ?? check.decided_by} small />
      <SummaryCell label="Обращений к LLM" value={check.llm_calls} />
      <SummaryCell label="Время проверки" value={`${(check.duration_ms / 1000).toFixed(1)} с`} />
    </div>
  );
}

function SummaryCell({ label, value, small }: { label: string; value: React.ReactNode; small?: boolean }) {
  return (
    <div className="bg-card px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("mt-0.5 text-foreground", small ? "text-sm" : "font-heading text-lg")}>{value}</p>
    </div>
  );
}

const STATUS_RING: Record<string, string> = {
  pass: "ring-success",
  fail: "ring-destructive",
  warn: "ring-warning",
  info: "ring-border",
};

function StatusIcon({ status }: { status: string }) {
  if (status === "pass") return <Check className="w-3.5 h-3.5 text-success" />;
  if (status === "fail") return <X className="w-3.5 h-3.5 text-destructive" />;
  if (status === "warn") return <CircleAlert className="w-3.5 h-3.5 text-warning" />;
  return <Minus className="w-3.5 h-3.5 text-muted-foreground" />;
}

function StepRow({ step, last, teacher }: { step: ProtocolStep; last: boolean; teacher: boolean }) {
  const [open, setOpen] = useState(step.status === "fail" || step.kind === "neural");
  const symbolic = step.kind === "symbolic";
  return (
    <li className="relative pl-11 pb-5">
      {!last && <span className="absolute left-[15px] top-8 bottom-0 w-px bg-border" aria-hidden />}
      <span
        className={cn(
          "absolute left-1 top-1.5 w-[22px] h-[22px] ring-2 ring-offset-2 ring-offset-card",
          symbolic ? "rounded-[4px] bg-symbolic" : "rounded-full bg-neural",
          STATUS_RING[step.status] ?? "ring-border"
        )}
        aria-hidden
      />
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-center gap-3 text-left"
      >
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-foreground flex items-center gap-2">
            {step.title} <StatusIcon status={step.status} />
          </p>
          <p className="text-xs text-muted-foreground">
            {symbolic ? "Символьный компонент" : "Нейросетевой компонент"}: {step.component}
            {step.duration_ms > 0 && <> — {step.duration_ms} мс</>}
          </p>
        </div>
        <ChevronDown className={cn("w-4 h-4 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="mt-3 rounded-md bg-surface/60 border border-border p-3 text-sm">
          <StepDetails step={step} teacher={teacher} />
        </div>
      )}
    </li>
  );
}

type Dict = Record<string, unknown>;

function StepDetails({ step, teacher }: { step: ProtocolStep; teacher: boolean }) {
  const d = step.details as Dict;
  if (Array.isArray(d.rules)) return <RulesTable rules={d.rules as Dict[]} />;
  if (Array.isArray(d.descriptions)) return <ImageDetails d={d} />;
  if (d.lab_match) return <LabMatchDetails m={d.lab_match as Dict} />;
  if (Object.keys(d).length === 1 && "error" in d) return <p className="text-destructive text-sm">Проверка прервана внутренней ошибкой ({String(d.error)}); отчёт передан преподавателю.</p>;
  if ("bits" in d) return <SimhashDetails d={d} teacher={teacher} />;
  if ("judge" in d) return <JudgeDetails d={d} />;
  if ("decision" in d) return <AggregationDetails d={d} />;
  if ("lemmas" in d) {
    return (
      <div className="space-y-2">
        <p className="text-muted-foreground">Слов: {String(d.words)}, значимых лемм: {String(d.lemmas)}</p>
        {Array.isArray(d.task_terms) && (d.task_terms as string[]).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">Ключевые понятия задания</p>
            <div className="flex flex-wrap gap-1">
              {(d.task_terms as string[]).map((t) => (
                <span key={t} className="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-foreground">{t}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }
  return <p className="text-muted-foreground">Сформировано пояснение ({String(d.length ?? "—")} символов)</p>;
}

function RulesTable({ rules }: { rules: Dict[] }) {
  return (
    <table className="w-full text-sm">
      <tbody>
        {rules.map((r) => (
          <tr key={String(r.rule_id)} className="border-b border-border/60 last:border-0 align-top">
            <td className="py-1.5 pr-2 text-xs text-muted-foreground w-8">{String(r.rule_id)}</td>
            <td className="py-1.5 pr-2 w-5"><StatusIcon status={r.outcome === "block" ? "fail" : String(r.outcome)} /></td>
            <td className="py-1.5">
              <span className="text-foreground">{String(r.title)}</span>
              <span className="block text-xs text-muted-foreground">{String(r.message)}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SimhashDetails({ d, teacher }: { d: Dict; teacher: boolean }) {
  const nearest = d.nearest as Dict | null;
  const bits = Number(d.bits);
  const maxH = Number(d.max_hamming);
  const threshold = 1 - maxH / bits;
  if (!nearest) {
    return <p className="text-muted-foreground">Других отчётов по этой лабораторной в индексе нет — сравнивать не с чем.</p>;
  }
  const sim = Number(nearest.similarity);
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Сходство с ближайшим отчётом другого студента</span>
        <span className="text-foreground">{(sim * 100).toFixed(0)}%</span>
      </div>
      <Meter value={sim} tone={sim >= threshold ? "danger" : "primary"} markers={[{ at: threshold, label: "порог" }]} />
      <p className="text-xs text-muted-foreground">
        Расстояние Хэмминга {String(nearest.hamming)} из {bits} бит; дубликатом считается расстояние ≤ {maxH}
        (сходство ≥ {(threshold * 100).toFixed(0)}%).
        {teacher && nearest.report_id != null && <> Ближайший отчёт № {String(nearest.report_id)}.</>}
      </p>
      {teacher && typeof d.fingerprint_hex === "string" && (
        <p className="text-xs text-muted-foreground">Отпечаток: <code className="text-foreground">{d.fingerprint_hex}</code></p>
      )}
    </div>
  );
}

function JudgeDetails({ d }: { d: Dict }) {
  if (!d.valid) {
    return <p className="text-destructive text-sm">Оценка не получена: {String(d.error ?? "ошибка модели")}. Агрегатор учитывает только валидные оценки.</p>;
  }
  const verdict = Boolean(d.verdict);
  const conf = Number(d.confidence ?? 0);
  const criteria = (d.criteria as Dict[] | undefined) ?? [];
  return (
    <div className="space-y-2.5">
      <div className="flex items-center gap-3">
        <span className={cn("text-sm font-semibold", verdict ? "text-success" : "text-destructive")}>
          {verdict ? "Соответствует" : "Не соответствует"}
        </span>
        <div className="flex-1"><Meter value={conf} tone="neural" /></div>
        <span className="text-xs text-muted-foreground w-28 text-right">уверенность {(conf * 100).toFixed(0)}%</span>
      </div>
      {d.summary ? <p className="text-foreground">{String(d.summary)}</p> : null}
      {d.model ? <p className="text-xs text-muted-foreground">Модель: {String(d.model)}</p> : null}
      {criteria.length > 0 && (
        <ul className="space-y-1">
          {criteria.map((c, i) => (
            <li key={i} className="flex gap-2 text-sm">
              <StatusIcon status={c.met === false ? "fail" : "pass"} />
              <span><span className="text-foreground">{String(c.name ?? "")}</span>
                {c.comment ? <span className="text-muted-foreground"> — {String(c.comment)}</span> : null}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function LabMatchDetails({ m }: { m: Dict }) {
  const t = m.thresholds as Dict | undefined;
  const target = m.target_similarity == null ? null : Number(m.target_similarity);
  const other = m.best_other_similarity == null ? null : Number(m.best_other_similarity);
  return (
    <div className="space-y-2">
      {target != null && (
        <>
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Сходство отчёта с заданием этой работы</span>
            <span className="text-foreground">{target.toFixed(2)}</span>
          </div>
          <Meter value={target} tone={m.doubt ? "warning" : "primary"}
            markers={t ? [{ at: Number(t.min_similarity), label: "порог" }] : undefined} />
        </>
      )}
      {other != null && (
        <p className="text-xs text-muted-foreground">
          Ближайшая другая лабораторная курса: {other.toFixed(2)} (сомнение, если она ближе на {String(t?.margin ?? "")} и более).
        </p>
      )}
      <p className="text-foreground">{String(m.reason ?? "")}</p>
    </div>
  );
}

function ImageDetails({ d }: { d: Dict }) {
  const items = d.descriptions as Dict[];
  const skipped = Number(d.skipped_by_limit ?? 0);
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        Изображений в отчёте: {String(d.images)}, описано: {String(d.described)}
        {Number(d.cached) > 0 && <> (из кэша: {String(d.cached)})</>}
        {skipped > 0 && <>; сверх ограничения в {String(d.max_images)} не описано: {skipped}</>}.
        Описания вставлены в текст на место рисунков и переданы оценщикам. Модель: {String(d.model)}.
      </p>
      <ul className="space-y-1.5">
        {items.map((it) => (
          <li key={String(it.index)} className="flex gap-2 text-sm">
            <span className="text-xs text-muted-foreground w-14 shrink-0 pt-0.5">Рис. {String(it.index)}</span>
            {it.valid
              ? <span className="text-foreground">{String(it.description)}</span>
              : <span className="text-muted-foreground">не описано: {String(it.error ?? "ошибка модели")}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

function AggregationDetails({ d }: { d: Dict }) {
  const score = d.score == null ? null : Number(d.score);
  return (
    <div className="space-y-2">
      {score != null && (
        <>
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Итоговая оценка «за принятие» P</span>
            <span className="text-foreground">{score.toFixed(2)}</span>
          </div>
          <Meter value={score} tone={score >= 0.65 ? "success" : score <= 0.35 ? "danger" : "warning"}
            markers={[{ at: 0.35, label: "порог отклонения" }, { at: 0.65, label: "порог принятия" }]} />
        </>
      )}
      {d.votes_for != null && (
        <p className="text-xs text-muted-foreground">Голоса: за — {String(d.votes_for)}, против — {String(d.votes_against)}; валидных оценок {String(d.valid)}.</p>
      )}
      <p className="text-foreground">Правило {String(d.rule)}: {String(d.reason)}</p>
    </div>
  );
}

function Legend() {
  return (
    <div className="flex flex-wrap gap-4 text-xs text-muted-foreground pt-1">
      <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-[2px] bg-symbolic" /> символьный шаг</span>
      <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-neural" /> нейросетевой шаг</span>
    </div>
  );
}
