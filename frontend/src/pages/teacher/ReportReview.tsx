import { Markdown } from "@/components/common/Markdown";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { errorMessage, reportsApi } from "@/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Loading, PageHeader, Panel, StatusBadge } from "@/components/common";
import { ProtocolView } from "@/components/protocol/ProtocolView";
import { formatDateTime } from "@/utils/constants";

export default function ReportReview() {
  const reportId = Number(useParams().reportId);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [comment, setComment] = useState("");
  const { data, isLoading } = useQuery({ queryKey: ["report", reportId], queryFn: () => reportsApi.get(reportId) });

  const decide = useMutation({
    mutationFn: (status: "approved" | "not-approved") => reportsApi.setStatus(reportId, status, comment),
    onSuccess: (_, status) => {
      toast.success(status === "approved" ? "Отчёт принят" : "Отчёт возвращён студенту");
      qc.invalidateQueries({ queryKey: ["t-queue"] });
      qc.invalidateQueries({ queryKey: ["report", reportId] });
      navigate("/teacher/reports");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (isLoading || !data) return <Loading />;
  const { report: r, check } = data;
  const open = r.status === "pending" || r.status === "manual-review";

  return (
    <div>
      <PageHeader back={{ to: "/teacher/reports", label: "Проверка отчётов" }}
        title={`${r.student_name}: лабораторная ${r.lab_number}`}
        description={`${r.course_title}, «${r.lab_title}». Отправлен ${formatDateTime(r.created_at)}.`}
        actions={<StatusBadge status={r.status} />} />
      <div className="grid lg:grid-cols-[1.1fr_1fr] gap-4 items-start">
        <div className="space-y-4">
          <Panel title="Текст отчёта" actions={
            r.source_type === "file"
              ? <Button size="sm" variant="outline" onClick={() => reportsApi.downloadFile(r).catch((e) => toast.error(errorMessage(e)))}>Скачать файл</Button>
              : r.url ? <a href={r.url} target="_blank" rel="noreferrer" className="text-sm text-primary hover:underline">Открыть в Google Docs</a> : null
          }>
            <div className="max-h-[520px] overflow-y-auto chat-scroll text-sm text-foreground/90 whitespace-pre-wrap leading-relaxed">
              {r.text || "Текст отчёта не сохранён (отчёт загружен до внедрения гибридной проверки)."}
            </div>
          </Panel>
          {open ? (
            <Panel title="Решение преподавателя">
              <div className="space-y-1.5">
                <Label htmlFor="cm">Комментарий для студента</Label>
                <Textarea id="cm" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Необязательно при принятии" />
              </div>
              <div className="flex gap-3 mt-4">
                <Button className="bg-success text-success-foreground hover:bg-success/90" disabled={decide.isPending} onClick={() => decide.mutate("approved")}>Принять</Button>
                <Button variant="outline" className="border-destructive/40 text-destructive hover:bg-destructive/10" disabled={decide.isPending || !comment.trim()}
                  onClick={() => decide.mutate("not-approved")} title={!comment.trim() ? "Укажите, что исправить" : undefined}>Вернуть на доработку</Button>
              </div>
            </Panel>
          ) : r.comment ? <Panel title="Комментарий"><p className="text-sm text-foreground">{r.comment}</p></Panel> : null}
        </div>
        <Panel title="Протокол автоматической проверки">
          {r.ai_summary && <Markdown className="mb-4">{r.ai_summary}</Markdown>}
          {check?.protocol ? <ProtocolView check={check} steps={check.protocol} teacher /> : <p className="text-sm text-muted-foreground">Протокол отсутствует.</p>}
        </Panel>
      </div>
    </div>
  );
}
