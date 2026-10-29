import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, FileText, Loader2, MessageSquarePlus, Mic, MicOff, Pencil, Pin, PinOff, Send, Trash2, Wrench } from "lucide-react";
import { toast } from "sonner";
import { chatApi, errorMessage, meApi, type ChatMessage, type ChatStreamEvent } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/common";
import { cn } from "@/lib/utils";
import { useSpeechInput } from "@/lib/speech";
import { messageDay, messageTime, messageTimeFull } from "@/utils/constants";

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
  const pin = useMutation({
    mutationFn: (v: { id: number; pinned: boolean }) => chatApi.pin(v.id, v.pinned),
    onSuccess: (_, v) => {
      toast.success(v.pinned ? "Диалог закреплён" : "Диалог откреплён");
      qc.invalidateQueries({ queryKey: ["me-chats"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  // голосовой ввод: промежуточный текст показывается в поле, окончательный дописывается к введённому
  const [spoken, setSpoken] = useState("");
  const voice = useSpeechInput(
    (t, final) => {
      if (final) { setText((prev) => (prev ? `${prev.trimEnd()} ${t}` : t)); setSpoken(""); }
      else setSpoken(t);
    },
    (message) => toast.error(message),
  );
  const draft = spoken ? `${text}${text ? " " : ""}${spoken}` : text;
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
      setMessages((p) => {
        if (!p.length) return p;
        const last = { ...p[p.length - 1], content: e.response, tools: e.tools, sources: e.sources, streaming: false,
          created_at: e.answered_at ?? new Date().toISOString() };
        const rest = p.slice(0, -1);
        // время вопроса — по часам сервера, как в сохранённой истории
        const q = rest[rest.length - 1];
        if (q?.role === "user" && e.asked_at) rest[rest.length - 1] = { ...q, created_at: e.asked_at };
        return [...rest, last];
      });
    else if (e.type === "error") throw new Error(e.detail);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    // вместе с напечатанным уходит и фраза, которую браузер ещё распознаёт
    const m = draft.trim();
    if (!m || active == null || pending) return;
    if (voice.listening) voice.cancel();
    setText("");
    setSpoken("");
    setPending(true);
    setMessages((p) => [...p, { role: "user", content: m, created_at: new Date().toISOString() },
      { role: "assistant", content: "", steps: [], streaming: true }]);
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
                    <button className="flex-1 min-w-0 flex items-center gap-1.5 text-left px-3 py-2 text-sm text-foreground" onClick={() => setActive(c.chat_id)}>
                      {c.pinned && <Pin className="w-3 h-3 shrink-0 text-primary" aria-label="Закреплён" />}
                      <span className="truncate">{c.name}</span>
                    </button>
                    <button className="p-1.5 text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100 [@media(hover:none)]:opacity-100 focus:opacity-100"
                      aria-label={c.pinned ? "Открепить" : "Закрепить"} title={c.pinned ? "Открепить" : "Закрепить"}
                      onClick={() => pin.mutate({ id: c.chat_id, pinned: !c.pinned })}>
                      {c.pinned ? <PinOff className="w-3.5 h-3.5" /> : <Pin className="w-3.5 h-3.5" />}
                    </button>
                    <button className="p-1.5 text-muted-foreground opacity-0 group-hover:opacity-100 [@media(hover:none)]:opacity-100 focus:opacity-100" aria-label="Переименовать"
                      onClick={() => setEditing({ id: c.chat_id, name: c.name })}><Pencil className="w-3.5 h-3.5" /></button>
                    <button className="p-1.5 text-muted-foreground opacity-0 group-hover:opacity-100 [@media(hover:none)]:opacity-100 focus:opacity-100 hover:text-destructive" aria-label="Удалить"
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
                  <div key={i}>
                  {/* разделитель дня: перед первым сообщением и при смене даты */}
                  {m.created_at && messageDay(m.created_at) !== messageDay(messages[i - 1]?.created_at) && (
                    <p className="text-center text-xs text-muted-foreground my-3">{messageDay(m.created_at)}</p>
                  )}
                  <div className={cn("flex flex-col", m.role === "user" ? "items-end" : "items-start")}>
                    <div className={cn("max-w-[85%] rounded-lg px-4 py-3 text-sm",
                      m.role === "user" ? "bg-primary text-primary-foreground" : "bg-surface border border-border text-foreground")}>
                      {m.role === "assistant" ? (
                        <>
                          {m.streaming && <StreamSteps steps={m.steps ?? []} writing={!!m.content} />}
                          {m.content && <div className="prose dark:prose-invert prose-sm max-w-none"><ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown></div>}
                          {(m.tools?.length || m.sources?.length) ? (
                            <div className="mt-3 pt-2 border-t border-border space-y-1 text-xs text-muted-foreground">
                              {m.tools && m.tools.length > 0 && <p className="flex gap-1.5"><Wrench className="w-3.5 h-3.5 shrink-0" /> {m.tools.join(", ")}</p>}
                              {m.sources && m.sources.length > 0 && <p className="flex gap-1.5"><FileText className="w-3.5 h-3.5 shrink-0" /> {m.sources.join(", ")}</p>}
                            </div>
                          ) : null}
                        </>
                      ) : <span className="whitespace-pre-wrap">{m.content}</span>}
                    </div>
                    {m.created_at && !m.streaming && (
                      <time dateTime={m.created_at} title={messageTimeFull(m.created_at)} className="mt-1 px-1 text-[11px] text-muted-foreground">
                        {messageTime(m.created_at)}
                      </time>
                    )}
                  </div>
                  </div>
                ))}
                <div ref={endRef} />
              </div>
              <form onSubmit={submit} className="border-t border-border p-3 flex gap-2">
                <Input value={draft} onChange={(e) => setText(e.target.value)}
                  placeholder={voice.listening ? "Говорите — текст появится здесь" : "Ваш вопрос"} aria-label="Сообщение"
                  disabled={pending} readOnly={!!spoken} />
                <Button type="button" variant={voice.listening ? "destructive" : "outline"} disabled={!voice.supported || pending}
                  onClick={() => (voice.listening ? voice.stop() : voice.start())}
                  aria-pressed={voice.listening}
                  aria-label={voice.listening ? "Остановить запись" : "Голосовой ввод"}
                  title={!voice.supported ? "Голосовой ввод работает в Chrome, Edge и Safari" : voice.listening ? "Остановить запись" : "Голосовой ввод"}>
                  {voice.listening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </Button>
                <Button type="submit" disabled={!draft.trim() || pending} aria-label="Отправить"><Send className="w-4 h-4" /></Button>
              </form>
              {voice.listening && (
                <p className="px-4 pb-2 -mt-1 text-xs text-muted-foreground flex items-center gap-1.5" aria-live="polite">
                  <span className="w-2 h-2 rounded-full bg-destructive animate-pulse" /> Идёт запись. Нажмите на микрофон ещё раз, чтобы закончить, затем отправьте вопрос.
                </p>
              )}
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
