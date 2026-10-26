import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, FileText, FlaskConical, Pencil, UserCheck, Users } from "lucide-react";
import { toast } from "sonner";
import { coursesApi, errorMessage, labsApi } from "@/api";
import { Button } from "@/components/ui/button";
import { Loading, PageHeader, Panel } from "@/components/common";
import { COURSE_TINTS, DIFFICULTY_MAP } from "@/utils/constants";

export default function CourseView() {
  const courseId = Number(useParams().id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const course = useQuery({ queryKey: ["course", courseId], queryFn: () => coursesApi.get(courseId) });
  const labs = useQuery({ queryKey: ["labs", courseId], queryFn: () => labsApi.list(courseId) });
  const students = useQuery({ queryKey: ["c-students", courseId], queryFn: () => coursesApi.students(courseId) });
  const requests = useQuery({ queryKey: ["c-requests", courseId], queryFn: () => coursesApi.requests(courseId) });
  const files = useQuery({ queryKey: ["files", courseId], queryFn: () => coursesApi.files(courseId) });

  const remove = useMutation({
    mutationFn: () => coursesApi.remove(courseId),
    onSuccess: () => { toast.success("Курс удалён"); qc.invalidateQueries({ queryKey: ["t-courses"] }); navigate("/teacher/courses"); },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (course.isLoading) return <Loading />;
  const c = course.data!;
  const diff = DIFFICULTY_MAP[c.difficulty] ?? DIFFICULTY_MAP.intermediate;
  const pending = (requests.data ?? []).filter((r) => r.status === "pending").length;
  const actions = [
    { to: "edit", icon: Pencil, label: "Описание и экзамен" },
    { to: "labs", icon: FlaskConical, label: `Лабораторные (${labs.data?.length ?? 0})` },
    { to: "files", icon: FileText, label: `Материалы (${files.data?.length ?? 0})` },
    { to: "students", icon: Users, label: `Студенты (${students.data?.length ?? 0})` },
    { to: "requests", icon: UserCheck, label: `Заявки (${pending})` },
    { to: "analytics", icon: BarChart3, label: "Аналитика" },
  ];

  return (
    <div>
      <PageHeader back={{ to: "/teacher/courses", label: "Курсы" }} title={c.title} />
      <div className="rounded-lg border border-border p-5 sm:p-6 mb-6" style={{ background: COURSE_TINTS[c.id % COURSE_TINTS.length] }}>
        <div className="flex flex-wrap gap-2 mb-3">
          <span className={`rounded-md border px-2 py-0.5 text-xs bg-black/20 ${diff.color}`}>{diff.label}</span>
          {c.tags.map((t) => <span key={t} className="rounded-md bg-black/20 px-2 py-0.5 text-xs text-white/80">{t}</span>)}
        </div>
        <p className="text-white/85 max-w-2xl">{c.description}</p>
        {!c.has_materials && <p className="mt-3 text-sm text-warning">Материалы не загружены: ассистент и генерация тестов недоступны студентам.</p>}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
        {actions.map((a) => (
          <Link key={a.to} to={a.to} className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3.5 hover:border-primary/50">
            <a.icon className="w-4 h-4 text-primary" /> <span className="text-sm text-foreground">{a.label}</span>
          </Link>
        ))}
      </div>
      <Panel title="Удаление курса" description="Будут удалены лабораторные, отчёты, результаты и векторное хранилище материалов.">
        <Button variant="outline" className="border-destructive/40 text-destructive hover:bg-destructive/10"
          onClick={() => { if (window.confirm(`Удалить курс «${c.title}» без возможности восстановления?`)) remove.mutate(); }}>
          Удалить курс
        </Button>
      </Panel>
    </div>
  );
}
