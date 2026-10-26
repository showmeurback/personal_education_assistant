import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserCheck } from "lucide-react";
import { toast } from "sonner";
import { coursesApi, errorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { EmptyState, PageHeader } from "@/components/common";
import { formatDateTime } from "@/utils/constants";

export default function Requests() {
  const courseId = Number(useParams().id);
  const qc = useQueryClient();
  const { data = [] } = useQuery({ queryKey: ["c-requests", courseId], queryFn: () => coursesApi.requests(courseId) });
  const pending = data.filter((r) => r.status === "pending");
  const refresh = (msg: string) => () => { toast.success(msg); qc.invalidateQueries({ queryKey: ["c-requests", courseId] }); qc.invalidateQueries({ queryKey: ["c-students", courseId] }); };
  const approve = useMutation({ mutationFn: coursesApi.approveRequest, onSuccess: refresh("Студент зачислен"), onError: (e) => toast.error(errorMessage(e)) });
  const reject = useMutation({ mutationFn: coursesApi.rejectRequest, onSuccess: refresh("Заявка отклонена"), onError: (e) => toast.error(errorMessage(e)) });

  return (
    <div className="max-w-3xl">
      <PageHeader back={{ to: `/teacher/courses/${courseId}`, label: "К курсу" }} title="Заявки на курс" description={`Ожидают решения: ${pending.length}`} />
      {pending.length ? (
        <ul className="rounded-lg border border-border divide-y divide-border bg-card">
          {pending.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <span className="flex-1 text-sm text-foreground">{r.last_name} {r.first_name}<span className="block text-xs text-muted-foreground">{formatDateTime(r.created_at)}</span></span>
              <Button size="sm" onClick={() => approve.mutate(r.id)} disabled={approve.isPending}>Зачислить</Button>
              <Button size="sm" variant="outline" onClick={() => reject.mutate(r.id)} disabled={reject.isPending}>Отклонить</Button>
            </li>
          ))}
        </ul>
      ) : <EmptyState icon={UserCheck} title="Новых заявок нет" />}
    </div>
  );
}
