import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, FlaskConical, Lock, Target } from "lucide-react";
import { toast } from "sonner";
import { coursesApi, errorMessage, labsApi, meApi, type WeakTopicsMap } from "@/api";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState, Loading, Meter, PageHeader, Panel, StatusBadge } from "@/components/common";
import { COURSE_TINTS, DIFFICULTY_MAP, formatDate } from "@/utils/constants";

export default function CoursePage() {
  const courseId = Number(useParams().id);
  const qc = useQueryClient();
  const course = useQuery({ queryKey: ["course", courseId], queryFn: () => coursesApi.get(courseId) });
  const enrolled = !!course.data?.enrolled;
  const labs = useQuery({ queryKey: ["labs", courseId], queryFn: () => labsApi.list(courseId), enabled: enrolled });
  const files = useQuery({ queryKey: ["files", courseId], queryFn: () => coursesApi.files(courseId), enabled: enrolled });
  const reports = useQuery({ queryKey: ["me-reports"], queryFn: meApi.reports, enabled: enrolled });
  const tests = useQuery({ queryKey: ["me-tests", courseId], queryFn: () => meApi.testResults(courseId), enabled: enrolled });
  const exams = useQuery({ queryKey: ["me-exams", courseId], queryFn: () => meApi.examResults(courseId), enabled: enrolled });

  const enroll = useMutation({
    mutationFn: () => coursesApi.requestAccess(courseId),
    onSuccess: () => {
      toast.success("Заявка отправлена преподавателю");
      qc.invalidateQueries({ queryKey: ["course", courseId] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (course.isLoading) return <Loading />;
  if (!course.data) return <EmptyState icon={Lock} title="Курс не найден" />;
  const c = course.data;
  const diff = DIFFICULTY_MAP[c.difficulty] ?? DIFFICULTY_MAP.intermediate;
  const lastReport = (labId: number) => reports.data?.find((r) => r.lab_id === labId);

  return (
    <div>
      <PageHeader back={{ to: "/student/my-courses", label: "Мои курсы" }} title={c.title} />
      <div className="dark rounded-lg border border-border p-5 sm:p-6 mb-6" style={{ background: COURSE_TINTS[c.id % COURSE_TINTS.length] }}>
        <div className="flex flex-wrap gap-2 mb-3">
          <span className={`rounded-md border px-2 py-0.5 text-xs bg-black/20 ${diff.color}`}>{diff.label}</span>
          {c.tags.map((t) => <span key={t} className="rounded-md bg-black/20 px-2 py-0.5 text-xs text-white/80">{t}</span>)}
        </div>
        <p className="text-white/85 max-w-2xl">{c.description}</p>
        {!enrolled && (
          <div className="mt-5">
            {c.request_status === "pending" ? (
              <p className="text-sm text-white/80">Заявка отправлена и ждёт решения преподавателя.</p>
            ) : (
              <Button onClick={() => enroll.mutate()} disabled={enroll.isPending}>
                {c.request_status === "rejected" ? "Отправить заявку повторно" : "Записаться на курс"}
              </Button>
            )}
          </div>
        )}
      </div>

      {!enrolled ? (
        <EmptyState icon={Lock} title="Материалы доступны после зачисления"
          text="Лабораторные, тесты, экзамен и ассистент откроются, когда преподаватель одобрит заявку." />
      ) : (
        <Tabs defaultValue="labs">
          <TabsList className="mb-5 flex-wrap h-auto">
            <TabsTrigger value="labs">Лабораторные</TabsTrigger>
            <TabsTrigger value="gaps">Что подтянуть</TabsTrigger>
            <TabsTrigger value="learn">Тесты и экзамен</TabsTrigger>
            <TabsTrigger value="chat">Ассистент</TabsTrigger>
            <TabsTrigger value="files">Материалы</TabsTrigger>
          </TabsList>

          <TabsContent value="labs">
            {labs.isLoading ? <Loading /> : labs.data?.length ? (
              <ul className="rounded-lg border border-border divide-y divide-border bg-card">
                {labs.data.map((lab) => {
                  const r = lastReport(lab.id);
                  return (
                    <li key={lab.id}>
                      <Link to={`/student/courses/${courseId}/labs/${lab.id}`} className="flex items-center gap-4 px-4 py-3.5 hover:bg-surface/60">
                        <span className="w-9 h-9 rounded-md bg-surface-2 flex items-center justify-center font-heading text-sm text-primary shrink-0">{lab.number}</span>
                        <span className="flex-1 min-w-0">
                          <span className="block text-sm font-medium text-foreground">{lab.title}</span>
                          <span className="block text-xs text-muted-foreground line-clamp-1">{lab.task}</span>
                        </span>
                        {r ? <StatusBadge status={r.status} /> : <span className="text-xs text-muted-foreground">не сдана</span>}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            ) : <EmptyState icon={FlaskConical} title="Лабораторных пока нет" />}
          </TabsContent>

          <TabsContent value="gaps">
            <WeakTopicsPanel courseId={courseId} hasMaterials={!!c.has_materials} />
          </TabsContent>

          <TabsContent value="learn" className="grid md:grid-cols-2 gap-4">
            <Panel title="Тест по материалам" description="Вопросы с вариантами ответа по выбранной теме."
              actions={<Link to={`/student/courses/${courseId}/test`}><Button size="sm">Пройти тест</Button></Link>}>
              {tests.data?.length ? (
                <ul className="text-sm space-y-1.5">
                  {tests.data.slice(0, 5).map((t) => (
                    <li key={t.id} className="flex justify-between gap-3">
                      <span className="text-foreground truncate">{t.topic ?? "Без темы"}</span>
                      <span className="text-muted-foreground shrink-0">{Math.round(t.percentage)}%, {formatDate(t.created_at)}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-muted-foreground">Тестов ещё не было.</p>}
            </Panel>
            <Panel title="Пробный экзамен" description="Письменные ответы оценивает языковая модель по шкале 0–100."
              actions={<Link to={`/student/courses/${courseId}/exam`}><Button size="sm">Начать</Button></Link>}>
              {exams.data?.length ? (
                <ul className="text-sm space-y-1.5">
                  {exams.data.slice(0, 5).map((e) => (
                    <li key={e.id} className="flex justify-between gap-3">
                      <span className="text-foreground">{e.total_questions} вопр.</span>
                      <span className="text-muted-foreground">{e.avg_score != null ? `${Math.round(e.avg_score)} из 100` : "—"}, {formatDate(e.created_at)}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-muted-foreground">Экзамен ещё не проходили.</p>}
            </Panel>
          </TabsContent>

          <TabsContent value="chat">
            <Panel title="Ассистент по материалам курса"
              description={c.has_materials ? "Задавайте вопросы — ответы строятся на загруженных лекциях, источники указываются."
                : "Преподаватель ещё не загрузил материалы, поэтому ассистент пока недоступен."}
              actions={c.has_materials ? <Link to={`/student/courses/${courseId}/chat`}><Button size="sm">Открыть чат</Button></Link> : undefined}>
              <p className="text-sm text-muted-foreground">Ассистент помнит предпочтения из профиля: например, «объясняй на примерах».</p>
            </Panel>
          </TabsContent>

          <TabsContent value="files">
            {files.data?.length ? (
              <ul className="rounded-lg border border-border divide-y divide-border bg-card">
                {files.data.map((f) => (
                  <li key={f.id} className="flex items-center gap-3 px-4 py-3">
                    <FileText className="w-4 h-4 text-muted-foreground" />
                    <span className="flex-1 text-sm text-foreground truncate">{f.filename}</span>
                    <Button variant="ghost" size="sm" onClick={() => coursesApi.downloadFile(courseId, f).catch((e) => toast.error(errorMessage(e)))}>
                      <Download className="w-4 h-4 mr-1.5" /> Скачать
                    </Button>
                  </li>
                ))}
              </ul>
            ) : <EmptyState icon={FileText} title="Материалов пока нет" />}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}

const TONE: Record<string, "danger" | "warning" | "primary"> = { "слабо": "danger", "нужно подтянуть": "warning" };

function WeakTopicsPanel({ courseId, hasMaterials }: { courseId: number; hasMaterials: boolean }) {
  // сначала мгновенная символьная карта, затем советы модели и фрагменты лекций
  const base = useQuery({ queryKey: ["weak-topics", courseId, "base"], queryFn: () => meApi.weakTopics(courseId, false) });
  const full = useQuery({ queryKey: ["weak-topics", courseId, "full"], queryFn: () => meApi.weakTopics(courseId, true),
    staleTime: 5 * 60_000, enabled: !!base.data && base.data.topics.length > 0 });
  if (base.isLoading) return <Loading />;
  const data: WeakTopicsMap | undefined = full.data ?? base.data;
  const advicePending = !full.data && full.isFetching;
  if (!data || data.evidence_total === 0) {
    return <EmptyState icon={Target} title="Пока нечего анализировать"
      text="Пройдите тест или пробный экзамен, сдайте лабораторную — и здесь появятся темы, которые стоит подтянуть." />;
  }
  return (
    <div className="space-y-4">
      {data.topics.length === 0 ? (
        <Panel title="Пробелов не найдено">
          <p className="text-sm text-muted-foreground">По всем темам, где есть результаты, уровень освоения не ниже 70 %.</p>
        </Panel>
      ) : data.topics.map((t) => (
        <Panel key={t.topic} title={t.topic}
          description={`Уровень освоения ${Math.round(t.mastery * 100)} % — ${t.level}. Основание: тестов ${t.evidence.test}, ответов экзамена ${t.evidence.exam}, отчётов ${t.evidence.lab}.`}>
          <Meter value={t.mastery} tone={TONE[t.level] ?? "primary"} markers={[{ at: 0.7, label: "порог" }]} />
          {t.advice ? <p className="mt-3 text-sm text-foreground">{t.advice}</p>
            : advicePending && <p className="mt-3 text-sm text-muted-foreground">Готовим совет по вашим ошибкам…</p>}
          {t.details.length > 0 && (
            <details className="mt-3">
              <summary className="cursor-pointer text-sm text-primary">Ваши ошибки по теме ({t.details.length})</summary>
              <ul className="mt-2 space-y-1 text-sm text-muted-foreground list-disc pl-5">
                {t.details.map((d, i) => <li key={i}>{d}</li>)}
              </ul>
            </details>
          )}
          {t.sources.length > 0 && (
            <div className="mt-3 space-y-1.5">
              <p className="text-xs text-muted-foreground">Что перечитать в материалах курса</p>
              {t.sources.map((s, i) => (
                <p key={i} className="text-sm"><span className="text-foreground">{s.filename}</span>
                  <span className="text-muted-foreground"> — «{s.snippet}…»</span></p>
              ))}
            </div>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <Link to={`/student/courses/${courseId}/test?topic=${encodeURIComponent(t.topic)}`}><Button size="sm">Пройти тест по теме</Button></Link>
            {hasMaterials && (
              <Link to={`/student/courses/${courseId}/chat?q=${encodeURIComponent(`Объясни тему «${t.topic}»: что важно понять и где я мог ошибиться?`)}`}>
                <Button size="sm" variant="outline">Спросить ассистента</Button>
              </Link>
            )}
          </div>
        </Panel>
      ))}
      {data.strong.length > 0 && (
        <p className="text-sm text-muted-foreground">Освоено хорошо: {data.strong.map((s) => `${s.topic} (${Math.round(s.mastery * 100)} %)`).join(", ")}.</p>
      )}
      <p className="text-xs text-muted-foreground">{data.method}{data.with_advice && !data.llm_used && data.topics.length > 0 ? " Советы сейчас недоступны: сервис искусственного интеллекта не ответил." : ""}</p>
    </div>
  );
}
