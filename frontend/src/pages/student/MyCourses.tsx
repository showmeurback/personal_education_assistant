import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { GraduationCap } from "lucide-react";
import { toast } from "sonner";
import { coursesApi, errorMessage, meApi } from "@/api";
import { CourseCard } from "@/components/course/CourseCard";
import { StarRating } from "@/components/course/StarRating";
import { EmptyState, Loading, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";

export default function MyCourses() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"active" | "done">("active");
  const { data = [], isLoading } = useQuery({ queryKey: ["me-courses"], queryFn: meApi.courses });
  const shown = data.filter((c) => (tab === "active" ? !c.is_completed : c.is_completed));

  const rate = async (id: number, r: number) => {
    try {
      await coursesApi.rate(id, r);
      toast.success(`Оценка ${r} из 5 сохранена`);
      qc.invalidateQueries({ queryKey: ["me-courses"] });
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <div>
      <PageHeader title="Мои курсы"
        description="Курс завершён, когда преподаватель принял все лабораторные и пройден пробный экзамен." />
      <div role="tablist" className="inline-flex rounded-md border border-border bg-card p-1 mb-6">
        {([["active", "Активные"], ["done", "Завершённые"]] as const).map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`px-4 py-1.5 rounded text-sm ${tab === k ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}>
            {label} ({data.filter((c) => (k === "active" ? !c.is_completed : c.is_completed)).length})
          </button>
        ))}
      </div>
      {isLoading ? <Loading /> : shown.length ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {shown.map((c) => (
            <CourseCard key={c.id} course={c} to={`/student/courses/${c.id}`}
              footer={
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Лабы: {c.labs_completed ? "сданы" : "в работе"}; экзамен: {c.exam_completed ? "пройден" : "нет"}</span>
                  {c.is_completed && <StarRating value={c.my_rating} onChange={(r) => rate(c.id, r)} size="sm" />}
                </div>
              } />
          ))}
        </div>
      ) : (
        <EmptyState icon={GraduationCap} title={tab === "active" ? "Нет активных курсов" : "Завершённых курсов пока нет"}
          action={tab === "active" ? <Link to="/student/catalog"><Button>Открыть каталог</Button></Link> : undefined} />
      )}
    </div>
  );
}
