import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { GraduationCap } from "lucide-react";
import { teacherApi } from "@/api";
import { CourseCard } from "@/components/course/CourseCard";
import { Button } from "@/components/ui/button";
import { EmptyState, Loading, PageHeader } from "@/components/common";

export default function TeacherCourses() {
  const { data = [], isLoading } = useQuery({ queryKey: ["t-courses"], queryFn: teacherApi.courses });
  return (
    <div>
      <PageHeader title="Курсы" actions={<Link to="/teacher/courses/new"><Button>Создать курс</Button></Link>} />
      {isLoading ? <Loading /> : data.length ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.map((c) => (
            <CourseCard key={c.id} course={c} to={`/teacher/courses/${c.id}`}
              footer={<p className="text-xs text-muted-foreground">Студентов: {c.students}; заявок: {c.pending_requests}; отчётов к проверке: {c.pending_reports}</p>} />
          ))}
        </div>
      ) : <EmptyState icon={GraduationCap} title="Курсов пока нет" action={<Link to="/teacher/courses/new"><Button>Создать курс</Button></Link>} />}
    </div>
  );
}
