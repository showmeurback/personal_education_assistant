import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { FileCheck2 } from "lucide-react";
import { teacherApi, type Report } from "@/api";
import { EmptyState, Loading, PageHeader, StatusBadge } from "@/components/common";
import { DECIDED_BY_MAP, formatDateTime } from "@/utils/constants";

export default function ReportsQueue() {
  const [tab, setTab] = useState<"queue" | "history">("queue");
  const queue = useQuery({ queryKey: ["t-queue"], queryFn: teacherApi.queue });
  const history = useQuery({ queryKey: ["t-history"], queryFn: teacherApi.history, enabled: tab === "history" });
  const data = tab === "queue" ? queue : history;

  return (
    <div>
      <PageHeader title="Проверка отчётов"
        description="Сначала показаны отчёты, по которым компоненты системы разошлись во мнениях." />
      <div role="tablist" className="inline-flex rounded-md border border-border bg-card p-1 mb-6">
        {([["queue", `Ждут решения (${queue.data?.length ?? 0})`], ["history", "Все отправки"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`px-4 py-1.5 rounded text-sm ${tab === k ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}>{l}</button>
        ))}
      </div>
      {data.isLoading ? <Loading /> : data.data?.length ? (
        <div className="rounded-lg border border-border bg-card overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="text-left text-xs text-muted-foreground border-b border-border">
                <th className="px-4 py-2.5 font-normal">Студент</th><th className="px-4 py-2.5 font-normal">Курс и лабораторная</th>
                <th className="px-4 py-2.5 font-normal">Система</th><th className="px-4 py-2.5 font-normal">Статус</th><th className="px-4 py-2.5 font-normal">Отправлен</th>
              </tr>
            </thead>
            <tbody>{data.data.map((r) => <Row key={r.report_id} r={r} />)}</tbody>
          </table>
        </div>
      ) : <EmptyState icon={FileCheck2} title={tab === "queue" ? "Все отчёты проверены" : "Отправок пока нет"} />}
    </div>
  );
}

function Row({ r }: { r: Report }) {
  return (
    <tr className="border-b border-border/60 last:border-0 hover:bg-surface/50">
      <td className="px-4 py-3"><Link to={`/teacher/reports/${r.report_id}`} className="text-foreground hover:text-primary">{r.student_name}</Link></td>
      <td className="px-4 py-3 text-muted-foreground">{r.course_title}<span className="block text-xs">Лабораторная {r.lab_number}. {r.lab_title}</span></td>
      <td className="px-4 py-3 text-xs text-muted-foreground">{r.check ? DECIDED_BY_MAP[r.check.decided_by] ?? r.check.decided_by : "—"}
        {r.check?.final_score != null && <span className="block">P = {r.check.final_score.toFixed(2)}</span>}</td>
      <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
      <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">{formatDateTime(r.created_at)}</td>
    </tr>
  );
}
