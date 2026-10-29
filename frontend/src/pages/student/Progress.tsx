import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { meApi } from "@/api";
import { PageHeader, Panel, StatTile, StatusBadge } from "@/components/common";
import { formatDate } from "@/utils/constants";

export default function Progress() {
  const tests = useQuery({ queryKey: ["me-tests"], queryFn: () => meApi.testResults() });
  const exams = useQuery({ queryKey: ["me-exams"], queryFn: () => meApi.examResults() });
  const reports = useQuery({ queryKey: ["me-reports"], queryFn: meApi.reports });
  const courses = useQuery({ queryKey: ["me-courses"], queryFn: meApi.courses });
  const title = (id: number) => courses.data?.find((c) => c.id === id)?.title ?? `Курс ${id}`;

  const t = tests.data ?? [];
  const e = exams.data ?? [];
  const avgT = t.length ? Math.round(t.reduce((s, x) => s + x.percentage, 0) / t.length) : null;
  const scored = e.filter((x) => x.avg_score != null);
  const avgE = scored.length ? Math.round(scored.reduce((s, x) => s + (x.avg_score ?? 0), 0) / scored.length) : null;

  return (
    <div>
      <PageHeader title="Успеваемость" description="Результаты тестов, экзаменов и статус отчётов по всем курсам." />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
        <StatTile label="Тестов" value={t.length} />
        <StatTile label="Средний результат тестов" value={avgT == null ? "—" : `${avgT}%`} tone="primary" />
        <StatTile label="Экзаменов" value={e.length} />
        <StatTile label="Средний балл экзаменов" value={avgE == null ? "—" : `${avgE} / 100`} tone="primary" />
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <Panel title="Тесты">
          {t.length ? (
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-muted-foreground"><th className="pb-2 pr-3 font-normal">Тема</th><th className="pb-2 pr-3 font-normal">Результат</th><th className="pb-2 font-normal">Дата</th></tr></thead>
              <tbody>{t.map((x) => (
                <tr key={x.id} className="border-t border-border">
                  <td className="py-2 pr-3 text-foreground">{x.topic ?? "—"}<span className="block text-xs text-muted-foreground">{title(x.course_id)}</span></td>
                  <td className={`py-2 pr-3 ${x.percentage >= 70 ? "text-success" : x.percentage >= 50 ? "text-warning" : "text-destructive"}`}>{Math.round(x.percentage)}%</td>
                  <td className="py-2 text-muted-foreground whitespace-nowrap">{formatDate(x.created_at)}</td>
                </tr>))}</tbody>
            </table>
          ) : <p className="text-sm text-muted-foreground">Тестов ещё не было.</p>}
        </Panel>
        <Panel title="Экзамены">
          {e.length ? (
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-muted-foreground"><th className="pb-2 pr-3 font-normal">Курс</th><th className="pb-2 pr-3 font-normal">Балл</th><th className="pb-2 font-normal">Дата</th></tr></thead>
              <tbody>{e.map((x) => (
                <tr key={x.id} className="border-t border-border">
                  <td className="py-2 pr-3 text-foreground">{title(x.course_id)}</td>
                  <td className={`py-2 pr-3 ${(x.avg_score ?? 0) >= 75 ? "text-success" : (x.avg_score ?? 0) >= 35 ? "text-warning" : "text-destructive"}`}>{x.avg_score == null ? "—" : `${Math.round(x.avg_score)} / 100`}</td>
                  <td className="py-2 text-muted-foreground whitespace-nowrap">{formatDate(x.created_at)}</td>
                </tr>))}</tbody>
            </table>
          ) : <p className="text-sm text-muted-foreground">Экзаменов ещё не было.</p>}
        </Panel>
        <Panel title="Отчёты по лабораторным" className="lg:col-span-2">
          {reports.data?.length ? (
            <ul className="divide-y divide-border">
              {reports.data.map((r) => (
                <li key={r.report_id} className="py-2.5 flex flex-wrap items-center gap-3">
                  <Link to={`/student/courses/${r.course_id}/labs/${r.lab_id}`} className="flex-1 min-w-0 text-sm text-foreground hover:text-primary">
                    {r.course_title}: лабораторная {r.lab_number} «{r.lab_title}»
                    <span className="block text-xs text-muted-foreground">{formatDate(r.created_at)}</span>
                  </Link>
                  <StatusBadge status={r.status} />
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-muted-foreground">Отчётов ещё не было.</p>}
        </Panel>
      </div>
    </div>
  );
}
