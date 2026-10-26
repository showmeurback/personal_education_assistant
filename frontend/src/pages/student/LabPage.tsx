import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, Link2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { errorMessage, labsApi, reportsApi, type Report } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loading, PageHeader, Panel, StatusBadge } from "@/components/common";
import { ProtocolView } from "@/components/protocol/ProtocolView";
import { formatDateTime } from "@/utils/constants";
import { cn } from "@/lib/utils";

const BLOCKING = new Set(["checking", "pending", "manual-review", "approved"]);

export default function LabPage() {
  const params = useParams();
  const courseId = Number(params.id);
  const labId = Number(params.labId);
  const qc = useQueryClient();
  const [mode, setMode] = useState<"file" | "url">("file");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  // отчёт, отправленный в этой сессии: его итог показывается отдельной карточкой
  const [watchId, setWatchId] = useState<number | null>(null);
  const [sentAt, setSentAt] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const lab = useQuery({ queryKey: ["lab", labId], queryFn: () => labsApi.get(labId) });
  const history = useQuery({
    queryKey: ["lab-reports", labId],
    queryFn: () => reportsApi.myLabReports(labId),
    // пока отчёт проверяется в фоне, история опрашивается каждые 2,5 с
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === "checking") ? 2500 : false),
  });

  const submit = useMutation({
    mutationFn: () => reportsApi.submit(labId, mode === "file" ? { file: file! } : { url: url.trim() }),
    onSuccess: (res) => {
      setWatchId(res.report_id);
      setSentAt(Date.now());
      setFile(null);
      setUrl("");
      qc.invalidateQueries({ queryKey: ["lab-reports", labId] });
      qc.invalidateQueries({ queryKey: ["me-reports"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (lab.isLoading) return <Loading />;
  if (!lab.data) return null;
  const l = lab.data;
  const latest = history.data?.[0];
  const locked = latest && BLOCKING.has(latest.status);
  const watched = watchId != null ? history.data?.find((r) => r.report_id === watchId) : undefined;
  const checking = latest?.status === "checking";
  const sections = (l.required_sections ?? "").split(/\n|;|,/).map((s) => s.trim()).filter(Boolean);

  return (
    <div className="max-w-3xl">
      <PageHeader back={{ to: `/student/courses/${courseId}`, label: "К курсу" }}
        title={`Лабораторная ${l.number}. ${l.title}`} />

      <Panel title="Задание" className="mb-5">
        <p className="text-foreground whitespace-pre-wrap leading-relaxed">{l.task || "Задание не указано."}</p>
        <div className="mt-4 pt-4 border-t border-border text-sm text-muted-foreground space-y-1">
          <p>Минимальный объём отчёта: {l.min_words ?? 120} слов.</p>
          {sections.length > 0 && <p>Обязательные разделы: {sections.map((s) => `«${s}»`).join(", ")}.</p>}
        </div>
      </Panel>

      {checking && <CheckingNotice since={latest!.report_id === watchId ? sentAt : null} />}
      {watched && watched.status !== "checking" && <SubmissionResult report={watched} />}

      {!locked ? (
        <Panel title="Сдать отчёт" description="Отчёт сначала проверяет система, затем — преподаватель." className="mb-5">
          <div role="tablist" className="inline-flex rounded-md border border-border p-1 mb-4">
            <button role="tab" aria-selected={mode === "file"} onClick={() => setMode("file")}
              className={cn("px-3 py-1.5 rounded text-sm flex items-center gap-1.5", mode === "file" ? "bg-surface-2 text-foreground" : "text-muted-foreground")}>
              <FileUp className="w-4 h-4" /> Файл
            </button>
            <button role="tab" aria-selected={mode === "url"} onClick={() => setMode("url")}
              className={cn("px-3 py-1.5 rounded text-sm flex items-center gap-1.5", mode === "url" ? "bg-surface-2 text-foreground" : "text-muted-foreground")}>
              <Link2 className="w-4 h-4" /> Google Docs
            </button>
          </div>

          {mode === "file" ? (
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) setFile(f); }}
              className="rounded-md border border-dashed border-border px-4 py-8 text-center"
            >
              <p className="text-sm text-foreground">{file ? file.name : "Перетащите файл сюда или выберите на компьютере"}</p>
              <p className="text-xs text-muted-foreground mt-1">PDF, DOCX или TXT, до 15 МБ</p>
              <Button variant="outline" size="sm" className="mt-3" onClick={() => inputRef.current?.click()}>Выбрать файл</Button>
              <input ref={inputRef} type="file" accept=".pdf,.docx,.txt" className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </div>
          ) : (
            <div className="space-y-1.5">
              <Label htmlFor="gdoc">Ссылка на документ</Label>
              <Input id="gdoc" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://docs.google.com/document/d/…" />
              <p className="text-xs text-muted-foreground">Откройте доступ «Все, у кого есть ссылка», иначе система не сможет прочитать отчёт.</p>
            </div>
          )}

          <Button className="mt-4" disabled={submit.isPending || (mode === "file" ? !file : !url.trim())} onClick={() => submit.mutate()}>
            {submit.isPending ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Отправка…</> : "Отправить на проверку"}
          </Button>
        </Panel>
      ) : (
        !watched && !checking && latest && (
          <Panel className="mb-5">
            <p className="text-sm text-muted-foreground">
              {latest.status === "approved" ? "Отчёт принят преподавателем." : "Отчёт на проверке у преподавателя. Новую версию можно будет отправить после его решения."}
            </p>
          </Panel>
        )
      )}

      {history.data && history.data.length > 0 && (
        <Panel title="История отправок">
          <ul className="divide-y divide-border">
            {history.data.map((r) => <HistoryItem key={r.report_id} report={r} />)}
          </ul>
        </Panel>
      )}
    </div>
  );
}

function CheckingNotice({ since }: { since: number | null }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const seconds = since != null ? Math.max(0, Math.round((now - since) / 1000)) : null;
  return (
    <section className="rounded-lg bg-card border border-neural/40 p-5 sm:p-6 mb-5" aria-live="polite">
      <div className="flex items-center gap-3">
        <Loader2 className="w-5 h-5 animate-spin text-neural" aria-hidden />
        <h2 className="font-body text-base font-semibold text-foreground">Отчёт проверяется</h2>
        {seconds != null && <span className="text-sm text-muted-foreground ml-auto">{seconds} с</span>}
      </div>
      <p className="text-sm text-muted-foreground mt-2">
        Правила и поиск заимствований, описание рисунков, три оценщика и арбитр. Обычно это занимает 15–40 секунд;
        страницу можно закрыть — результат сохранится в истории отправок.
      </p>
    </section>
  );
}

function SubmissionResult({ report }: { report: Report }) {
  const decision = report.check?.decision;
  const tone = decision === "approve" ? "border-success/40" : decision === "reject" ? "border-destructive/40" : "border-warning/40";
  return (
    <section className={cn("rounded-lg bg-card border p-5 sm:p-6 mb-5", tone)} aria-live="polite">
      <div className="flex items-center justify-between gap-3 mb-2">
        <h2 className="font-body text-base font-semibold text-foreground">Результат проверки</h2>
        <StatusBadge status={report.status} />
      </div>
      {report.ai_summary && <p className="text-foreground whitespace-pre-wrap">{report.ai_summary}</p>}
      {report.check?.protocol && (
        <details className="mt-4">
          <summary className="cursor-pointer text-sm text-primary">Как система пришла к решению</summary>
          <div className="mt-4">
            <ProtocolView check={report.check} steps={report.check.protocol} />
          </div>
        </details>
      )}
    </section>
  );
}

function HistoryItem({ report }: { report: Report }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="py-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-foreground flex-1 min-w-0 truncate">
          {report.filename ?? report.url ?? "Отчёт"}
          <span className="block text-xs text-muted-foreground">{formatDateTime(report.created_at)}</span>
        </span>
        <StatusBadge status={report.status} />
        {report.check?.protocol && (
          <button className="text-xs text-primary hover:underline" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
            {open ? "Скрыть протокол" : "Протокол"}
          </button>
        )}
      </div>
      {report.comment && <p className="text-sm text-foreground mt-2">Комментарий преподавателя: {report.comment}</p>}
      {report.status === "ai-rejected" && report.ai_summary && !open && (
        <p className="text-sm text-muted-foreground mt-2 whitespace-pre-wrap line-clamp-3">{report.ai_summary}</p>
      )}
      {open && report.check?.protocol && (
        <div className="mt-4">
          {report.ai_summary && <p className="text-sm text-foreground mb-3 whitespace-pre-wrap">{report.ai_summary}</p>}
          <ProtocolView check={report.check} steps={report.check.protocol} />
        </div>
      )}
    </li>
  );
}
