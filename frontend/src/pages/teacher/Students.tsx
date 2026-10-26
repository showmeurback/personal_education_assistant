import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { coursesApi } from "@/api";
import { EmptyState, PageHeader } from "@/components/common";

export default function Students() {
  const courseId = Number(useParams().id);
  const { data = [] } = useQuery({ queryKey: ["c-students", courseId], queryFn: () => coursesApi.students(courseId) });
  return (
    <div className="max-w-3xl">
      <PageHeader back={{ to: `/teacher/courses/${courseId}`, label: "К курсу" }} title="Студенты курса" description={`Зачислено: ${data.length}`} />
      {data.length ? (
        <ul className="rounded-lg border border-border divide-y divide-border bg-card">
          {[...data].sort((a, b) => a.last_name.localeCompare(b.last_name, "ru")).map((s) => (
            <li key={s.id} className="px-4 py-3 text-sm text-foreground">{s.last_name} {s.first_name}</li>
          ))}
        </ul>
      ) : <EmptyState icon={Users} title="Студентов пока нет" text="Студенты появятся после одобрения заявок." />}
    </div>
  );
}
