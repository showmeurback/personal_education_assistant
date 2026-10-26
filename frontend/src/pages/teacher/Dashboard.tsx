import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { GraduationCap } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { teacherApi } from "@/api";
import { CourseCard } from "@/components/course/CourseCard";
import { Button } from "@/components/ui/button";
import { EmptyState, PageHeader, Panel, StatTile, StatusBadge } from "@/components/common";
import { formatDateTime } from "@/utils/constants";

export default function TeacherDashboard() {
  const { name } = useAuthStore();
  const courses = useQuery({ queryKey: ["t-courses"], queryFn: teacherApi.courses });
  const queue = useQuery({ queryKey: ["t-queue"], queryFn: teacherApi.queue });
  const list = courses.data ?? [];
  const q = queue.data ?? [];
  const manual = q.filter((r) => r.status === "manual-review").length;

  return (
    <div>
      <PageHeader title={`Здравствуйте, ${name.split(" ")[0]}`} description="Курсы и отчёты, ожидающие вашего решения." />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
        <StatTile label="Курсов" value={list.length} />
        <StatTile label="Студентов на курсах" value={list.reduce((s, c) => s + c.students, 0)} />
        <StatTile label="Отчётов к проверке" value={q.length} tone="primary" />
        <StatTile label="Из них спорных" value={manual} tone={manual ? "warning" : "default"} hint="Компоненты системы разошлись" />
      </div>

      {q.length > 0 && (
        <Panel title="Очередь проверки" className="mb-8" actions={<Link to="/teacher/reports" className="text-sm text-primary hover:underline">Вся очередь</Link>}>
          <ul className="divide-y divide-border">
            {q.slice(0, 5).map((r) => (
              <li key={r.report_id}>
                <Link to={`/teacher/reports/${r.report_id}`} className="py-2.5 flex flex-wrap items-center gap-3 hover:text-primary">
                  <span className="flex-1 min-w-0 text-sm">
                    <span className="text-foreground">{r.student_name}</span>
                    <span className="text-muted-foreground">, {r.course_title}, лабораторная {r.lab_number}</span>
                    <span className="block text-xs text-muted-foreground">{formatDateTime(r.created_at)}</span>
                  </span>
                  <StatusBadge status={r.status} />
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="flex items-center justify-between mb-3">
        <h2 className="font-body text-base font-semibold text-foreground">Курсы</h2>
        <Link to="/teacher/courses/new"><Button size="sm">Создать курс</Button></Link>
      </div>
      {list.length ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {list.map((c) => (
            <CourseCard key={c.id} course={c} to={`/teacher/courses/${c.id}`}
              footer={<p className="text-xs text-muted-foreground">Студентов: {c.students}; заявок: {c.pending_requests}; отчётов к проверке: {c.pending_reports}</p>} />
          ))}
        </div>
      ) : <EmptyState icon={GraduationCap} title="Курсов пока нет" action={<Link to="/teacher/courses/new"><Button>Создать первый курс</Button></Link>} />}
    </div>
  );
}
