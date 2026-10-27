import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Loader2, Send } from "lucide-react";
import { toast } from "sonner";
import { errorMessage, examApi, type ExamEvaluation, type ExamQuestion } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { PageHeader, Panel } from "@/components/common";
import { EXAM_VERDICT_MAP } from "@/utils/constants";

interface Entry { question: ExamQuestion; answer?: string; evaluation?: ExamEvaluation }

export default function ExamPage() {
  const courseId = Number(useParams().id);
  const [count, setCount] = useState(3);
  const [examId, setExamId] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [avg, setAvg] = useState<number | null | undefined>(undefined);
  const endRef = useRef<HTMLDivElement>(null);

  // тело в фигурных скобках: эффект не должен возвращать результат scrollIntoView (в новых браузерах — Promise)
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [entries, busy]);

  const start = async () => {
    setBusy(true);
    try {
      const r = await examApi.start(courseId, count);
      setExamId(r.exam_id); setTotal(r.total_questions); setEntries([{ question: r.question }]); setAvg(undefined);
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };

  const send = async () => {
    if (!examId || !input.trim()) return;
    const answer = input.trim();
    setInput("");
    setBusy(true);
    try {
      const r = await examApi.answer(courseId, examId, answer);
      setEntries((prev) => {
        const next = [...prev];
        next[next.length - 1] = { ...next[next.length - 1], answer, evaluation: r.evaluation };
        if (r.next_question) next.push({ question: r.next_question });
        return next;
      });
      if (r.completed) setAvg((await examApi.summary(courseId, examId)).avg_score);
    } catch (e) { toast.error(errorMessage(e)); setInput(answer); } finally { setBusy(false); }
  };

  const back = { to: `/student/courses/${courseId}`, label: "К курсу" };
  if (!examId) {
    return (
      <div className="max-w-3xl">
        <PageHeader back={back} title="Пробный экзамен"
          description="Отвечайте письменно своими словами. Каждый ответ получает оценку от 0 до 100, категорию и рекомендацию." />
        <Panel>
          <div className="flex items-end gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="cnt">Вопросов (1–10)</Label>
              <Input id="cnt" type="number" min={1} max={10} value={count} className="w-24"
                onChange={(e) => setCount(Math.max(1, Math.min(10, Number(e.target.value) || 1)))} />
            </div>
            <Button onClick={start} disabled={busy}>{busy ? "Готовим вопросы…" : "Начать экзамен"}</Button>
          </div>
        </Panel>
      </div>
    );
  }

  const done = avg !== undefined;
  return (
    <div className="max-w-3xl">
      <PageHeader back={back} title="Пробный экзамен"
        description={done ? "Экзамен завершён." : `Вопрос ${entries.length} из ${total}`} />
      <div className="space-y-4">
        {entries.map((e, i) => (
          <Panel key={i}>
            <p className="text-xs text-muted-foreground mb-1">Вопрос {i + 1}</p>
            <p className="text-foreground font-medium">{e.question.text}</p>
            {e.answer && <p className="mt-3 text-sm text-foreground/90 whitespace-pre-wrap border-l-2 border-border pl-3">{e.answer}</p>}
            {e.evaluation && <Evaluation ev={e.evaluation} />}
          </Panel>
        ))}
        {done && (
          <Panel>
            <p className="text-foreground">Средний балл: <span className="font-heading text-xl">{avg == null ? "—" : Math.round(avg)}</span> из 100</p>
            <Button className="mt-4" variant="outline" onClick={() => { setExamId(null); setEntries([]); }}>Пройти ещё раз</Button>
          </Panel>
        )}
        {!done && (
          <div className="space-y-2">
            <Textarea rows={4} value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ваш ответ"
              aria-label="Ответ на вопрос" disabled={busy}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send(); }} />
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Ctrl+Enter — отправить</span>
              <Button onClick={send} disabled={busy || !input.trim()}>
                {busy ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Оцениваем…</> : <><Send className="w-4 h-4 mr-2" /> Ответить</>}
              </Button>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}

function Evaluation({ ev }: { ev: ExamEvaluation }) {
  const v = EXAM_VERDICT_MAP[ev.verdict] ?? EXAM_VERDICT_MAP.incorrect;
  return (
    <div className="mt-4 rounded-md bg-surface/60 border border-border p-3 text-sm space-y-1.5">
      <p className="flex items-center gap-3">
        <span className="font-semibold" style={{ color: v.color }}>{v.label}</span>
        <span className="text-foreground">{ev.score ?? "—"} из 100</span>
      </p>
      {ev.summary && <p className="text-foreground">{ev.summary}</p>}
      {ev.issues.length > 0 && <ul className="list-disc pl-5 text-muted-foreground">{ev.issues.map((x) => <li key={x}>{x}</li>)}</ul>}
      <p className="text-muted-foreground">Рекомендация: {ev.recommendation}</p>
    </div>
  );
}
