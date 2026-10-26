import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { coursesApi } from "@/api";
import { Loading, PageHeader, Panel, StatTile } from "@/components/common";
import { DECIDED_BY_MAP, EXAM_VERDICT_MAP } from "@/utils/constants";

const AXIS = { fill: "#8fa3c8", fontSize: 12 };
const TT = { contentStyle: { background: "#0f1b36", border: "1px solid #213560", borderRadius: 6, color: "#e7edf8", fontSize: 13 } };
const DIFF: Record<string, string> = { easy: "Лёгкий", medium: "Средний", hard: "Сложный" };
const DECISION: Record<string, string> = { approve: "Принять", reject: "Отклонить", manual_review: "Ручная проверка" };

function avg(xs: (number | null)[]) {
  const v = xs.filter((x): x is number => x != null);
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
}
function Empty({ text }: { text: string }) { return <p className="text-sm text-muted-foreground py-8 text-center">{text}</p>; }

export default function Analytics() {
  const courseId = Number(useParams().id);
  const { data, isLoading } = useQuery({ queryKey: ["analytics", courseId], queryFn: () => coursesApi.analytics(courseId) });
  if (isLoading || !data) return <Loading />;

  const avgTest = avg(data.test_averages.map((s) => s.avg_percentage));
  const avgExam = avg(data.exam_averages.map((s) => s.avg_score));
  const approved = data.lab_funnel.reduce((s, l) => s + l.approved, 0);
  const slots = data.lab_funnel.reduce((s, l) => s + l.enrolled, 0);
  const weak = data.topic_accuracy.filter((t) => t.accuracy_pct < 60).length;

  const byDate: Record<string, number[]> = {};
  for (const r of data.test_timeline) {
    const d = new Date(r.created_at.replace(" ", "T"));
    const k = d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
    (byDate[k] ??= []).push(r.percentage ?? 0);
  }
  const timeline = Object.entries(byDate).map(([date, v]) => ({ date, avg: Math.round(v.reduce((a, b) => a + b, 0) / v.length) }));
  const verdicts = data.verdict_distribution.map((v) => ({ name: EXAM_VERDICT_MAP[v.verdict]?.label ?? v.verdict, value: v.count, color: EXAM_VERDICT_MAP[v.verdict]?.color ?? "#8fa3c8" }));
  const verification = data.verification.map((v) => ({
    name: `${DECISION[v.decision] ?? v.decision}: ${DECIDED_BY_MAP[v.decided_by] ?? v.decided_by}`,
    count: v.count, ms: Math.round(v.avg_ms), llm: v.avg_llm_calls.toFixed(1),
  }));

  return (
    <div>
      <PageHeader back={{ to: `/teacher/courses/${courseId}`, label: "К курсу" }} title="Аналитика курса" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatTile label="Средний результат тестов" value={avgTest == null ? "—" : `${Math.round(avgTest)}%`} />
        <StatTile label="Средний балл экзамена" value={avgExam == null ? "—" : `${Math.round(avgExam)} / 100`} />
        <StatTile label="Лабораторных принято" value={slots ? `${Math.round((approved / slots) * 100)}%` : "—"} hint={`${approved} из ${slots}`} tone="success" />
        <StatTile label="Слабых тем" value={weak} hint="точность ниже 60%" tone={weak ? "danger" : "default"} />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Panel title="Автоматическая проверка отчётов" description="Сколько решений приняли символьные компоненты, а сколько — ансамбль оценщиков." className="lg:col-span-2">
          {verification.length ? (
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-muted-foreground"><th className="pb-2 font-normal">Решение и кем принято</th><th className="pb-2 font-normal text-right">Отчётов</th><th className="pb-2 font-normal text-right">Среднее время</th><th className="pb-2 font-normal text-right">Обращений к LLM</th></tr></thead>
              <tbody>{verification.map((v) => (
                <tr key={v.name} className="border-t border-border"><td className="py-2 text-foreground">{v.name}</td><td className="py-2 text-right">{v.count}</td><td className="py-2 text-right text-muted-foreground">{(v.ms / 1000).toFixed(1)} с</td><td className="py-2 text-right text-muted-foreground">{v.llm}</td></tr>
              ))}</tbody>
            </table>
          ) : <Empty text="Отчёты ещё не проходили автоматическую проверку" />}
        </Panel>

        <Panel title="Точность по темам тестов" className="lg:col-span-2">
          {data.topic_accuracy.length ? (
            <ResponsiveContainer width="100%" height={Math.max(160, data.topic_accuracy.length * 40)}>
              <BarChart data={data.topic_accuracy} layout="vertical" margin={{ left: 8, right: 44 }}>
                <XAxis type="number" domain={[0, 100]} tick={AXIS} axisLine={false} tickLine={false} unit="%" />
                <YAxis type="category" dataKey="topic" width={180} tick={AXIS} axisLine={false} tickLine={false} />
                <Tooltip {...TT} formatter={(v) => [`${v}%`, "Точность"]} />
                <Bar dataKey="accuracy_pct" radius={[0, 4, 4, 0]} maxBarSize={26}>
                  {data.topic_accuracy.map((t, i) => <Cell key={i} fill={t.accuracy_pct < 60 ? "#f0556a" : t.accuracy_pct < 80 ? "#f2b544" : "#3b7bff"} />)}
                  <LabelList dataKey="accuracy_pct" position="right" formatter={(v) => `${v}%`} style={{ fill: "#8fa3c8", fontSize: 12 }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty text="Нет данных по тестам" />}
        </Panel>

        <Panel title="Сдача лабораторных" description="По последней попытке каждого студента">
          {data.lab_funnel.length ? (
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={data.lab_funnel.map((l) => ({ name: `ЛР ${l.number}`, "Сдали": l.submitted, "Принято": l.approved, "Отклонено": l.rejected }))}>
                <CartesianGrid stroke="#213560" vertical={false} />
                <XAxis dataKey="name" tick={AXIS} axisLine={false} tickLine={false} />
                <YAxis tick={AXIS} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip {...TT} /><Legend wrapperStyle={{ fontSize: 12, color: "#8fa3c8" }} />
                <Bar dataKey="Сдали" fill="#3b7bff" radius={[3, 3, 0, 0]} maxBarSize={20} />
                <Bar dataKey="Принято" fill="#2ebd85" radius={[3, 3, 0, 0]} maxBarSize={20} />
                <Bar dataKey="Отклонено" fill="#f0556a" radius={[3, 3, 0, 0]} maxBarSize={20} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty text="Лабораторных нет" />}
        </Panel>

        <Panel title="Ответы на экзамене" description="Категории оценок по всем вопросам">
          {verdicts.length ? (
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={verdicts}>
                <XAxis dataKey="name" tick={AXIS} axisLine={false} tickLine={false} />
                <YAxis tick={AXIS} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip {...TT} formatter={(v) => [v, "ответов"]} />
                <Bar dataKey="value" radius={[3, 3, 0, 0]} maxBarSize={56}>{verdicts.map((v, i) => <Cell key={i} fill={v.color} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty text="Экзаменов пока нет" />}
        </Panel>

        <Panel title="Средний результат тестов по дням">
          {timeline.length ? (
            <ResponsiveContainer width="100%" height={210}>
              <LineChart data={timeline}>
                <CartesianGrid stroke="#213560" vertical={false} />
                <XAxis dataKey="date" tick={AXIS} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={AXIS} axisLine={false} tickLine={false} unit="%" />
                <Tooltip {...TT} formatter={(v) => [`${v}%`, "Средний результат"]} />
                <Line type="monotone" dataKey="avg" stroke="#3b7bff" strokeWidth={2.5} dot={{ r: 3, fill: "#3b7bff" }} />
              </LineChart>
            </ResponsiveContainer>
          ) : <Empty text="Нет активности" />}
        </Panel>

        <Panel title="Результаты по сложности тестов">
          {data.difficulty_breakdown.length ? (
            <ResponsiveContainer width="100%" height={210}>
              <BarChart data={data.difficulty_breakdown.map((d) => ({ name: DIFF[d.difficulty] ?? d.difficulty, avg: d.avg_pct }))}>
                <XAxis dataKey="name" tick={AXIS} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={AXIS} axisLine={false} tickLine={false} unit="%" />
                <Tooltip {...TT} formatter={(v) => [`${v}%`, "Средний результат"]} />
                <Bar dataKey="avg" fill="#3b7bff" radius={[3, 3, 0, 0]} maxBarSize={56} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty text="Нет данных" />}
        </Panel>

        <Panel title="Сложные вопросы тестов" description="Доля верных ответов ниже 70%" className="lg:col-span-2">
          {data.hard_questions.filter((q) => q.success_rate < 70).length ? (
            <ul className="divide-y divide-border">
              {data.hard_questions.filter((q) => q.success_rate < 70).slice(0, 8).map((q, i) => (
                <li key={i} className="py-2.5 flex gap-4 text-sm">
                  <span className="flex-1 text-foreground">{q.question_text}<span className="block text-xs text-muted-foreground">{q.topic}</span></span>
                  <span className={q.success_rate < 40 ? "text-destructive" : "text-warning"}>{q.success_rate}%</span>
                </li>
              ))}
            </ul>
          ) : <Empty text="Сложных вопросов не выявлено" />}
        </Panel>

        <Panel title="Студенты" className="lg:col-span-2">
          <StudentsTable data={data} />
        </Panel>
      </div>
    </div>
  );
}

function StudentsTable({ data }: { data: NonNullable<Awaited<ReturnType<typeof coursesApi.analytics>>> }) {
  const rows = new Map<number, { name: string; tests: number; t: number | null; exams: number; e: number | null }>();
  for (const s of data.test_averages) rows.set(s.student_id, { name: `${s.last_name} ${s.first_name}`, tests: s.test_count, t: s.avg_percentage, exams: 0, e: null });
  for (const s of data.exam_averages) {
    const r = rows.get(s.student_id) ?? { name: `${s.last_name} ${s.first_name}`, tests: 0, t: null, exams: 0, e: null };
    r.exams = s.exam_count; r.e = s.avg_score; rows.set(s.student_id, r);
  }
  const list = [...rows.values()].sort((a, b) => (b.t ?? -1) - (a.t ?? -1));
  if (!list.length) return <Empty text="Нет данных по студентам" />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm min-w-[520px]">
        <thead><tr className="text-left text-xs text-muted-foreground"><th className="pb-2 font-normal">Студент</th><th className="pb-2 font-normal text-right">Тестов</th><th className="pb-2 font-normal text-right">Средний %</th><th className="pb-2 font-normal text-right">Экзаменов</th><th className="pb-2 font-normal text-right">Средний балл</th></tr></thead>
        <tbody>{list.map((r) => (
          <tr key={r.name} className="border-t border-border">
            <td className="py-2 text-foreground">{r.name}</td>
            <td className="py-2 text-right text-muted-foreground">{r.tests || "—"}</td>
            <td className={`py-2 text-right ${r.t == null ? "" : r.t >= 80 ? "text-success" : r.t >= 60 ? "text-warning" : "text-destructive"}`}>{r.t == null ? "—" : `${Math.round(r.t)}%`}</td>
            <td className="py-2 text-right text-muted-foreground">{r.exams || "—"}</td>
            <td className="py-2 text-right">{r.e == null ? "—" : `${Math.round(r.e)} / 100`}</td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}
