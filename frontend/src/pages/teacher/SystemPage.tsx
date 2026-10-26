import { useQuery } from "@tanstack/react-query";
import { systemApi, teacherApi } from "@/api";
import { Loading, PageHeader, Panel } from "@/components/common";
import { PipelineHero } from "@/components/landing/PipelineHero";
import { DECIDED_BY_MAP } from "@/utils/constants";

const DECISION: Record<string, string> = { approve: "Принять", reject: "Отклонить", manual_review: "Ручная проверка" };

export default function SystemPage() {
  const cfg = useQuery({ queryKey: ["sys-config"], queryFn: systemApi.config });
  const stats = useQuery({ queryKey: ["t-vstats"], queryFn: teacherApi.verificationStats });
  if (cfg.isLoading || !cfg.data) return <Loading />;
  const c = cfg.data;
  const total = (stats.data ?? []).reduce((s, x) => s + x.count, 0);
  const noLlm = (stats.data ?? []).filter((x) => x.decided_by === "rules" || x.decided_by === "simhash").reduce((s, x) => s + x.count, 0);

  return (
    <div>
      <PageHeader title="О системе" description="Компоненты гибридной проверки, их настройки и статистика по вашим курсам." />
      <Panel className="mb-4"><PipelineHero /></Panel>
      <div className="grid lg:grid-cols-2 gap-4">
        <Panel title="Нейросетевой компонент">
          <dl className="text-sm grid grid-cols-[180px_1fr] gap-x-3 gap-y-2">
            <dt className="text-muted-foreground">Провайдер</dt><dd className="text-foreground">{c.llm.provider}</dd>
            <dt className="text-muted-foreground">Модель ассистента</dt><dd className="text-foreground break-all">{c.llm.model}</dd>
            {c.llm.judge_models ? (<>
              <dt className="text-muted-foreground">Строгий оценщик</dt><dd className="text-foreground break-all">{c.llm.judge_models.strict}</dd>
              <dt className="text-muted-foreground">Объективный оценщик</dt><dd className="text-foreground break-all">{c.llm.judge_models.objective}</dd>
              <dt className="text-muted-foreground">Лояльный оценщик</dt><dd className="text-foreground break-all">{c.llm.judge_models.loyal}</dd>
            </>) : (
              <><dt className="text-muted-foreground">Модель оценщиков</dt><dd className="text-foreground break-all">{c.llm.judge_model}</dd></>
            )}
            {c.llm.feedback_model && <><dt className="text-muted-foreground">Пояснения</dt><dd className="text-foreground break-all">{c.llm.feedback_model}</dd></>}
            {c.vision && <><dt className="text-muted-foreground">Описание рисунков</dt><dd className="text-foreground break-all">{c.vision.enabled ? `${c.vision.model} (до ${c.vision.max_images} на отчёт)` : "выключено"}</dd></>}
            <dt className="text-muted-foreground">Эмбеддинги</dt><dd className="text-foreground break-all">{c.embeddings.provider}: {c.embeddings.model}</dd>
            <dt className="text-muted-foreground">Ключ API</dt><dd className={c.llm.configured ? "text-success" : "text-destructive"}>{c.llm.configured ? "настроен" : "не задан"}</dd>
          </dl>
        </Panel>
        <Panel title="Символьный компонент">
          <dl className="text-sm grid grid-cols-[220px_1fr] gap-y-2">
            <dt className="text-muted-foreground">Отпечаток SimHash</dt><dd className="text-foreground">{c.verification.simhash_bits} бит, шинглы по {c.verification.simhash_shingle} леммы</dd>
            <dt className="text-muted-foreground">Порог дубликата</dt><dd className="text-foreground">Хэмминг ≤ {c.verification.duplicate_max_hamming}</dd>
            <dt className="text-muted-foreground">Минимум слов по умолчанию</dt><dd className="text-foreground">{c.verification.default_min_words}</dd>
            <dt className="text-muted-foreground">Пороги арбитра</dt><dd className="text-foreground">отклонить ≤ {c.verification.reject_threshold}, принять ≥ {c.verification.approve_threshold}</dd>
            <dt className="text-muted-foreground">Минимум валидных оценок</dt><dd className="text-foreground">{c.verification.min_valid_judges} из 3</dd>
          </dl>
        </Panel>
        <Panel title="Решения по вашим курсам" className="lg:col-span-2"
          description={total ? `Всего проверок: ${total}; без обращения к языковой модели решено ${noLlm} (${Math.round((noLlm / total) * 100)}%).` : undefined}>
          {stats.data?.length ? (
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-muted-foreground"><th className="pb-2 font-normal">Решение</th><th className="pb-2 font-normal">Кем принято</th><th className="pb-2 font-normal text-right">Отчётов</th><th className="pb-2 font-normal text-right">Среднее время</th><th className="pb-2 font-normal text-right">LLM-вызовов</th></tr></thead>
              <tbody>{stats.data.map((s) => (
                <tr key={s.decision + s.decided_by} className="border-t border-border">
                  <td className="py-2 text-foreground">{DECISION[s.decision] ?? s.decision}</td>
                  <td className="py-2 text-muted-foreground">{DECIDED_BY_MAP[s.decided_by] ?? s.decided_by}</td>
                  <td className="py-2 text-right">{s.count}</td>
                  <td className="py-2 text-right text-muted-foreground">{(s.avg_ms / 1000).toFixed(1)} с</td>
                  <td className="py-2 text-right text-muted-foreground">{s.avg_llm_calls.toFixed(1)}</td>
                </tr>))}</tbody>
            </table>
          ) : <p className="text-sm text-muted-foreground">Отчёты ещё не проверялись.</p>}
        </Panel>
      </div>
    </div>
  );
}
