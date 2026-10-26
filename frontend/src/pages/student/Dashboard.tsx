import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { BookOpen } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { meApi } from "@/api";
import { CourseCard } from "@/components/course/CourseCard";
import { Button } from "@/components/ui/button";
import { EmptyState, PageHeader, Panel, StatTile, StatusBadge } from "@/components/common";
import { formatDate } from "@/utils/constants";

export default function StudentDashboard() {
  const { name } = useAuthStore();
  const courses = useQuery({ queryKey: ["me-courses"], queryFn: meApi.courses });
  const tests = useQuery({ queryKey: ["me-tests"], queryFn: () => meApi.testResults() });
  const reports = useQuery({ queryKey: ["me-reports"], queryFn: meApi.reports });

  const list = courses.data ?? [];
  const avg = tests.data?.length
    ? Math.round(tests.data.reduce((s, t) => s + t.percentage, 0) / tests.data.length)
    : null;
  const needAction = (reports.data ?? []).filter((r) => r.status === "ai-rejected" || r.status === "not-approved");
  const active = list.filter((c) => !c.is_completed);

  return (
    <div>
      <PageHeader title={`Здравствуйте, ${name.split(" ")[0]}`} description="Что происходит в ваших курсах." />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
        <StatTile label="Курсов" value={list.length} />
        <StatTile label="Завершено" value={list.filter((c) => c.is_completed).length} tone="success" />
        <StatTile label="Тестов пройдено" value={tests.data?.length ?? 0} />
        <StatTile label="Средний результат тестов" value={avg === null ? "—" : `${avg}%`} tone="primary" />
      </div>

      {needAction.length > 0 && (
        <Panel title="Отчёты, которые нужно доработать" className="mb-8">
          <ul className="divide-y divide-border">
            {needAction.slice(0, 5).map((r) => (
              <li key={r.report_id} className="py-3 flex flex-wrap items-center gap-3">
                <div className="flex-1 min-w-0">
                  <Link to={`/student/courses/${r.course_id}/labs/${r.lab_id}`} className="text-sm text-foreground hover:text-primary">
                    {r.course_title}: лабораторная {r.lab_number} «{r.lab_title}»
                  </Link>
                  <p className="text-xs text-muted-foreground">{formatDate(r.created_at)}</p>
                </div>
                <StatusBadge status={r.status} />
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="flex items-center justify-between mb-3">
        <h2 className="font-body text-base font-semibold text-foreground">Активные курсы</h2>
        <Link to="/student/my-courses" className="text-sm text-primary hover:underline">Все мои курсы</Link>
      </div>
      {active.length > 0 ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {active.slice(0, 6).map((c) => <CourseCard key={c.id} course={c} to={`/student/courses/${c.id}`} />)}
        </div>
      ) : (
        <EmptyState icon={BookOpen} title={list.length ? "Все курсы завершены" : "Вы ещё не записаны на курсы"}
          text="Выберите курс в каталоге и отправьте заявку преподавателю."
          action={<Link to="/student/catalog"><Button>Открыть каталог</Button></Link>} />
      )}
    </div>
  );
}
