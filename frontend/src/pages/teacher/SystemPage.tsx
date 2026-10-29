import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { systemApi, teacherApi } from "@/api";
import { Loading, PageHeader, Panel } from "@/components/common";
import { PipelineHero } from "@/components/landing/PipelineHero";
import { DECIDED_BY_MAP } from "@/utils/constants";

const DECISION: Record<string, string> = { approve: "Принят", reject: "Отклонён", manual_review: "Передан преподавателю" };

/** Шаги проверки в том порядке, в каком их проходит отчёт. */
const STEPS = [
  { title: "Формальные требования", text: "Объём, обязательные разделы и связь с темой задания — то, что вы указали в настройках лабораторной.", ai: false },
  { title: "Поиск списывания", text: "Отчёт сравнивается с отчётами других студентов по этой же работе. Почти полное совпадение — отказ без дальнейшей проверки.", ai: false },
  { title: "Описание рисунков", text: "Скриншоты, графики, фотографии опытов и схемы описываются словами, чтобы их учли следующие шаги.", ai: true },
  { title: "Три проверяющих", text: "Искусственный интеллект трижды читает отчёт — строго, объективно и доброжелательно — и сверяет его с заданием, как комиссия.", ai: true },
  { title: "Итоговое решение", text: "Если проверяющие согласны и уверены, отчёт принимается или отклоняется автоматически. В остальных случаях решение за вами.", ai: false },
];

export default function SystemPage() {
  const cfg = useQuery({ queryKey: ["sys-config"], queryFn: systemApi.config });
  const stats = useQuery({ queryKey: ["t-vstats"], queryFn: teacherApi.verificationStats });
  if (cfg.isLoading || !cfg.data) return <Loading />;
  const c = cfg.data;
  const v = c.verification;
  const total = (stats.data ?? []).reduce((s, x) => s + x.count, 0);
  const noLlm = (stats.data ?? []).filter((x) => x.decided_by === "rules" || x.decided_by === "simhash").reduce((s, x) => s + x.count, 0);
  const copyPct = Math.round((1 - v.duplicate_max_hamming / v.simhash_bits) * 100);
  const pct = (x: number) => `${Math.round(x * 100)}%`;

  return (
    <div>
      <PageHeader title="О системе" description="Как система проверяет отчёты студентов и что решается без вашего участия." />

      <Panel className="mb-4" title="Как проверяется отчёт">
        <PipelineHero />
        <ol className="mt-5 grid sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {STEPS.map((s, i) => (
            <li key={s.title} className="text-sm">
              <p className="flex items-start gap-2 font-semibold text-foreground">
                <span className={s.ai ? "mt-1 w-3 h-3 shrink-0 rounded-full bg-neural" : "mt-1 w-3 h-3 shrink-0 rounded-[2px] bg-symbolic"} aria-hidden />
                {i + 1}. {s.title}
              </p>
              <p className="mt-1 text-muted-foreground leading-relaxed">{s.text}</p>
            </li>
          ))}
        </ol>
        <p className="mt-4 text-xs text-muted-foreground">
          Квадрат — проверка по точным правилам, круг — искусственный интеллект. Каждое решение сопровождается протоколом:
          его можно открыть на странице отчёта и увидеть, почему отчёт принят или отклонён.
        </p>
      </Panel>

      <div className="grid lg:grid-cols-2 gap-4">
        <Panel title="Правила проверки">
          <dl className="text-sm space-y-3">
            <Row term="Списывание">Отчёт отклоняется, если совпадает с отчётом другого студента по той же работе на {copyPct}% и более.</Row>
            <Row term="Объём">Если в настройках лабораторной не указано иное, отчёт должен содержать не менее {v.default_min_words} слов.</Row>
            <Row term="Автоматическое решение">Отчёт принимается при итоговой оценке от {pct(v.approve_threshold)} и отклоняется при оценке до {pct(v.reject_threshold)}. Всё, что между, передаётся вам.</Row>
            <Row term="Надёжность">Решение принимается, только если ответили хотя бы {v.min_valid_judges} проверяющих из 3. При сбое или задержке сервиса ИИ отчёт тоже передаётся вам.</Row>
          </dl>
        </Panel>

        <Panel title="Искусственный интеллект">
          <dl className="text-sm space-y-3">
            <Row term="Подключение">
              <span className={c.llm.configured ? "text-success" : "text-destructive"}>
                {c.llm.configured ? "работает" : "не настроено — обратитесь к администратору"}
              </span>
            </Row>
            <Row term="Ассистент студентов">Отвечает на вопросы по загруженным вами материалам курса и показывает, из каких файлов взят ответ.</Row>
            <Row term="Проверка отчётов">Три проверяющих и пояснения студентам при отказе.</Row>
            <Row term="Рисунки в отчётах">{c.vision?.enabled ? `Описываются, до ${c.vision.max_images} на отчёт.` : "Не описываются (функция выключена)."}</Row>
          </dl>
        </Panel>

        <Panel title="Решения по вашим курсам" className="lg:col-span-2"
          description={total ? `Всего проверок: ${total}. Без обращения к ИИ, только по правилам, решено ${noLlm} (${Math.round((noLlm / total) * 100)}%).` : undefined}>
          {stats.data?.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-muted-foreground"><th className="pb-2 font-normal">Результат</th><th className="pb-2 font-normal">Что решило</th><th className="pb-2 font-normal text-right">Отчётов</th><th className="pb-2 font-normal text-right">Среднее время</th><th className="pb-2 font-normal text-right">Обращений к ИИ</th></tr></thead>
                <tbody>{stats.data.map((s) => (
                  <tr key={s.decision + s.decided_by} className="border-t border-border">
                    <td className="py-2 text-foreground">{DECISION[s.decision] ?? s.decision}</td>
                    <td className="py-2 text-muted-foreground">{DECIDED_BY_MAP[s.decided_by] ?? s.decided_by}</td>
                    <td className="py-2 text-right">{s.count}</td>
                    <td className="py-2 text-right text-muted-foreground">{(s.avg_ms / 1000).toFixed(1)} с</td>
                    <td className="py-2 text-right text-muted-foreground">{s.avg_llm_calls.toFixed(1)}</td>
                  </tr>))}</tbody>
              </table>
            </div>
          ) : <p className="text-sm text-muted-foreground">Отчёты ещё не проверялись.</p>}
        </Panel>

        <details className="group lg:col-span-2 rounded-lg border border-border bg-card">
          <summary className="flex items-center justify-between cursor-pointer list-none px-5 py-4 text-sm font-medium text-foreground">
            Технические подробности (для администратора)
            <ChevronDown className="w-4 h-4 text-muted-foreground transition-transform group-open:rotate-180" />
          </summary>
          <div className="grid lg:grid-cols-2 gap-6 px-5 pb-5">
            <dl className="text-sm grid grid-cols-[170px_1fr] gap-x-3 gap-y-2 content-start">
              <dt className="col-span-2 text-xs text-muted-foreground">Нейросетевой компонент</dt>
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
              {c.vision && <><dt className="text-muted-foreground">Модель зрения</dt><dd className="text-foreground break-all">{c.vision.enabled ? c.vision.model : "выключена"}</dd></>}
              <dt className="text-muted-foreground">Эмбеддинги</dt><dd className="text-foreground break-all">{c.embeddings.provider}: {c.embeddings.model}</dd>
              <dt className="text-muted-foreground">Ключ API</dt><dd className={c.llm.configured ? "text-success" : "text-destructive"}>{c.llm.configured ? "настроен" : "не задан"}</dd>
            </dl>
            <dl className="text-sm grid grid-cols-[210px_1fr] gap-x-3 gap-y-2 content-start">
              <dt className="col-span-2 text-xs text-muted-foreground">Символьный компонент</dt>
              <dt className="text-muted-foreground">Отпечаток SimHash</dt><dd className="text-foreground">{v.simhash_bits} бит, шинглы по {v.simhash_shingle} леммы</dd>
              <dt className="text-muted-foreground">Порог дубликата</dt><dd className="text-foreground">расстояние Хэмминга ≤ {v.duplicate_max_hamming}</dd>
              <dt className="text-muted-foreground">Пороги арбитра</dt><dd className="text-foreground">отклонить ≤ {v.reject_threshold}, принять ≥ {v.approve_threshold}</dd>
              <dt className="text-muted-foreground">Минимум валидных оценок</dt><dd className="text-foreground">{v.min_valid_judges} из 3</dd>
              <dt className="text-muted-foreground">Минимум слов по умолчанию</dt><dd className="text-foreground">{v.default_min_words}</dd>
            </dl>
          </div>
        </details>
      </div>
    </div>
  );
}

function Row({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div className="grid sm:grid-cols-[170px_1fr] gap-x-3 gap-y-0.5">
      <dt className="text-muted-foreground">{term}</dt>
      <dd className="text-foreground leading-relaxed">{children}</dd>
    </div>
  );
}
