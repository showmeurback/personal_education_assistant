import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, FileText, Loader2, MessageSquarePlus, Pencil, Send, Trash2, Wrench } from "lucide-react";
import { toast } from "sonner";
import { chatApi, errorMessage, meApi, type ChatMessage, type ChatStreamEvent } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/common";
import { cn } from "@/lib/utils";

export default function ChatPage() {
  const courseId = Number(useParams().id);
  const qc = useQueryClient();
  const [active, setActive] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [searchParams] = useSearchParams();
  // вопрос, подготовленный «Картой пробелов» (?q=…), подставляется в поле ввода
  const [text, setText] = useState(searchParams.get("q") ?? "");
  const [editing, setEditing] = useState<{ id: number; name: string } | null>(null);
  const [pending, setPending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  // при уходе со страницы поток прерывается; сервер всё равно допишет ответ и сохранит его в истории
  useEffect(() => () => abortRef.current?.abort(), []);

  const chats = useQuery({ queryKey: ["me-chats"], queryFn: meApi.chats });
  const courseChats = (chats.data ?? []).filter((c) => c.course_id === courseId);

  useEffect(() => {
    if (active == null) return;
    abortRef.current?.abort();
    chatApi.history(active).then(setMessages).catch(() => setMessages([]));
  }, [active]);
  // тело в фигурных скобках: в новых браузерах scrollIntoView возвращает Promise, и React принял бы его
  // за функцию очистки эффекта (TypeError: … is not a function при следующем обновлении).
  // Во время потокового ответа прокрутка мгновенная, иначе плавная анимация не успевает за текстом.
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: pending ? "auto" : "smooth", block: "end" }); }, [messages, pending]);

  const create = useMutation({
    mutationFn: () => chatApi.create(courseId),
    onSuccess: (r) => { setActive(r.chat_id); setMessages([]); qc.invalidateQueries({ queryKey: ["me-chats"] }); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (id: number) => chatApi.remove(id),
    onSuccess: (_, id) => { if (active === id) { setActive(null); setMessages([]); } qc.invalidateQueries({ queryKey: ["me-chats"] }); },
  });
  const rename = useMutation({
    mutationFn: (v: { id: number; name: string }) => chatApi.rename(v.id, v.name),
    onSuccess: () => { setEditing(null); qc.invalidateQueries({ queryKey: ["me-chats"] }); },
  });

  /** Изменение последнего сообщения (ответа ассистента, который сейчас генерируется). */
  const updateLast = (f: (m: ChatMessage) => ChatMessage) =>
    setMessages((p) => (p.length ? [...p.slice(0, -1), f(p[p.length - 1])] : p));

  const onEvent = (e: ChatStreamEvent) => {
    if (e.type === "step") updateLast((m) => ({ ...m, steps: [...(m.steps ?? []), e.text] }));
    else if (e.type === "token") updateLast((m) => ({ ...m, content: m.content + e.text }));
    else if (e.type === "reset") updateLast((m) => ({ ...m, content: "" }));
    else if (e.type === "done")
      updateLast((m) => ({ ...m, content: e.response, tools: e.tools, sources: e.sources, streaming: false }));
    else if (e.type === "error") throw new Error(e.detail);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const m = text.trim();
    if (!m || active == null || pending) return;
    setText("");
    setPending(true);
    setMessages((p) => [...p, { role: "user", content: m }, { role: "assistant", content: "", steps: [], streaming: true }]);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await chatApi.sendStream(active, m, onEvent, controller.signal);
      qc.invalidateQueries({ queryKey: ["me-chats"] });
    } catch (err) {
      if (controller.signal.aborted) return;
      toast.error(errorMessage(err));
      setMessages((p) => p.slice(0, -2));
      setText(m);
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setPending(false);
    }
  };

  return (
    <div>
      <PageHeader back={{ to: `/student/courses/${courseId}`, label: "К курсу" }} title="Ассистент по курсу" />
      <div className="grid md:grid-cols-[240px_1fr] gap-4 md:h-[calc(100vh-13rem)] min-h-[480px]">
        <aside className="flex flex-col gap-2 min-h-0">
          <Button variant="outline" onClick={() => create.mutate()} disabled={create.isPending} className="justify-start">
            <MessageSquarePlus className="w-4 h-4 mr-2" /> Новый диалог
          </Button>
          <ul className="flex-1 overflow-y-auto space-y-0.5 chat-scroll">
            {courseChats.map((c) => (
              <li key={c.chat_id} className="group">
                {editing?.id === c.chat_id ? (
                  <form onSubmit={(e) => { e.preventDefault(); if (editing.name.trim()) rename.mutate(editing); }}>
                    <Input autoFocus value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                      onBlur={() => setEditing(null)} className="h-8 text-sm" aria-label="Название диалога" />
                  </form>
                ) : (
                  <div className={cn("flex items-center rounded-md", active === c.chat_id ? "bg-surface-2" : "hover:bg-surface")}>
                    <button className="flex-1 text-left px-3 py-2 text-sm truncate text-foreground" onClick={() => setActive(c.chat_id)}>{c.name}</button>
                    <button className="p-1.5 text-muted-foreground opacity-0 group-hover:opacity-100 focus:opacity-100" aria-label="Переименовать"
                      onClick={() => setEditing({ id: c.chat_id, name: c.name })}><Pencil className="w-3.5 h-3.5" /></button>
                    <button className="p-1.5 text-muted-foreground opacity-0 group-hover:opacity-100 focus:opacity-100 hover:text-destructive" aria-label="Удалить"
                      onClick={() => remove.mutate(c.chat_id)}><Trash2 className="w-3.5 h-3.5" /></button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </aside>

        <section className="flex flex-col rounded-lg border border-border bg-card min-h-0">
          {active == null ? (
            <div className="flex-1 flex items-center justify-center p-8 text-center">
              <div>
                <p className="text-foreground font-medium">Выберите диалог или начните новый</p>
                <p className="text-sm text-muted-foreground mt-1 max-w-sm">Ассистент ищет ответ в материалах курса и показывает, какие файлы использовал.</p>
              </div>
            </div>
          ) : (
            <>
              <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5 chat-scroll">
                {messages.length === 0 && <p className="text-sm text-muted-foreground">Задайте вопрос по курсу, например: «Объясни разницу между процессом и потоком».</p>}
                {messages.map((m, i) => (
                  <div key={i} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                    <div className={cn("max-w-[85%] rounded-lg px-4 py-3 text-sm",
                      m.role === "user" ? "bg-primary text-primary-foreground" : "bg-surface border border-border text-foreground")}>
                      {m.role === "assistant" ? (
                        <>
                          {m.streaming && <StreamSteps steps={m.steps ?? []} writing={!!m.content} />}
                          {m.content && <div className="prose prose-invert prose-sm max-w-none"><ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown></div>}
                          {(m.tools?.length || m.sources?.length) ? (
                            <div className="mt-3 pt-2 border-t border-border space-y-1 text-xs text-muted-foreground">
                              {m.tools && m.tools.length > 0 && <p className="flex gap-1.5"><Wrench className="w-3.5 h-3.5 shrink-0" /> {m.tools.join(", ")}</p>}
                              {m.sources && m.sources.length > 0 && <p className="flex gap-1.5"><FileText className="w-3.5 h-3.5 shrink-0" /> {m.sources.join(", ")}</p>}
                            </div>
                          ) : null}
                        </>
                      ) : <span className="whitespace-pre-wrap">{m.content}</span>}
                    </div>
                  </div>
                ))}
                <div ref={endRef} />
              </div>
              <form onSubmit={submit} className="border-t border-border p-3 flex gap-2">
                <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ваш вопрос" aria-label="Сообщение" disabled={pending} />
                <Button type="submit" disabled={!text.trim() || pending} aria-label="Отправить"><Send className="w-4 h-4" /></Button>
              </form>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

/** Ход работы ассистента: выполненные шаги с отметкой, текущий — с индикатором. */
function StreamSteps({ steps, writing }: { steps: string[]; writing: boolean }) {
  const shown = steps.length ? steps : ["Отправляю вопрос"];
  if (writing) {
    return <p className="flex items-center gap-2 text-xs text-muted-foreground mb-2"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Пишу ответ…</p>;
  }
  return (
    <ul className="space-y-1 text-xs text-muted-foreground" aria-live="polite">
      {shown.map((step, i) => (
        <li key={i} className="flex items-start gap-2">
          {i < shown.length - 1
            ? <Check className="w-3.5 h-3.5 mt-0.5 shrink-0 text-success" />
            : <Loader2 className="w-3.5 h-3.5 mt-0.5 shrink-0 animate-spin" />}
          <span className={i === shown.length - 1 ? "text-foreground" : undefined}>{step}</span>
        </li>
      ))}
    </ul>
  );
}
