import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Check, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { errorMessage, testsApi, type GeneratedTest, type TestSubmitResult } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Chip, PageHeader, Panel } from "@/components/common";
import { TEST_DIFFICULTY_MAP } from "@/utils/constants";
import { cn } from "@/lib/utils";

export default function TestPage() {
  const courseId = Number(useParams().id);
  const [params] = useSearchParams();
  const [topic, setTopic] = useState(params.get("topic") ?? "");
  const [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState("medium");
  const [test, setTest] = useState<GeneratedTest | null>(null);
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState<string[]>([]);
  const [result, setResult] = useState<TestSubmitResult | null>(null);

  const generate = useMutation({
    mutationFn: () => testsApi.generate(courseId, { topic: topic.trim(), num_questions: count, difficulty }),
    onSuccess: (t) => { setTest(t); setIdx(0); setAnswers(Array(t.questions.length).fill("")); setResult(null); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const submit = useMutation({
    mutationFn: () => testsApi.submit(test!.test_id, answers),
    onSuccess: setResult,
    onError: (e) => toast.error(errorMessage(e)),
  });

  const back = { to: `/student/courses/${courseId}`, label: "К курсу" };

  if (result && test) {
    return (
      <div className="max-w-3xl">
        <PageHeader back={back} title="Результат теста" />
        <Panel className="mb-5">
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
            <p className="font-heading text-4xl text-foreground">{Math.round(result.percentage)}%</p>
            <p className="text-muted-foreground">{result.correct_answers} из {result.total_questions} верно</p>
            <p className="text-foreground">Оценка {result.grade} из 10 — {result.grade_description}</p>
          </div>
        </Panel>
        <Panel title="Разбор ответов">
          <ol className="space-y-4">
            {result.results.map((r) => (
              <li key={r.question_num} className="text-sm">
                <p className="text-foreground font-medium flex gap-2">
                  {r.is_correct ? <Check className="w-4 h-4 text-success shrink-0 mt-0.5" /> : <X className="w-4 h-4 text-destructive shrink-0 mt-0.5" />}
                  {r.question_num}. {r.question_text}
                </p>
                <p className="pl-6 text-muted-foreground">Ваш ответ: {r.user_answer}) {r.options[r.user_answer] ?? "—"}</p>
                {!r.is_correct && <p className="pl-6 text-success">Верно: {r.correct_answer}) {r.options[r.correct_answer]}</p>}
                {!r.is_correct && r.explanation && (
                  <p className="pl-6 mt-1 text-foreground/90 border-l-2 border-neural/50 ml-6 pl-3">{r.explanation}</p>
                )}
              </li>
            ))}
          </ol>
          <div className="mt-6 flex gap-3">
            <Button variant="outline" onClick={() => { setTest(null); setResult(null); }}>Новый тест</Button>
          </div>
        </Panel>
      </div>
    );
  }

  if (test) {
    const q = test.questions[idx];
    const allAnswered = answers.every(Boolean);
    return (
      <div className="max-w-3xl">
        <PageHeader back={back} title={`Тест: ${topic}`} description={`Вопрос ${idx + 1} из ${test.questions.length}`} />
        <div className="h-1.5 rounded-full bg-surface-2 mb-6"><div className="h-full rounded-full bg-primary" style={{ width: `${((idx + 1) / test.questions.length) * 100}%` }} /></div>
        <Panel>
          <h2 className="font-body text-lg font-semibold text-foreground mb-5">{q.text}</h2>
          <fieldset className="space-y-2">
            <legend className="sr-only">Варианты ответа</legend>
            {Object.entries(q.options).map(([key, text]) => (
              <label key={key} className={cn("flex items-start gap-3 rounded-md border px-4 py-3 cursor-pointer",
                answers[idx] === key ? "border-primary bg-primary/10" : "border-border hover:border-primary/40")}>
                <input type="radio" name={`q${idx}`} value={key} checked={answers[idx] === key} className="mt-1 accent-[var(--primary)]"
                  onChange={() => setAnswers((p) => p.map((a, i) => (i === idx ? key : a)))} />
                <span className="text-foreground"><span className="text-muted-foreground mr-1.5">{key})</span>{text}</span>
              </label>
            ))}
          </fieldset>
          <div className="flex justify-between mt-6">
            <Button variant="outline" disabled={idx === 0} onClick={() => setIdx(idx - 1)}>Назад</Button>
            {idx < test.questions.length - 1 ? (
              <Button disabled={!answers[idx]} onClick={() => setIdx(idx + 1)}>Следующий вопрос</Button>
            ) : (
              <Button disabled={!allAnswered || submit.isPending} onClick={() => submit.mutate()}>
                {submit.isPending ? "Проверяем…" : "Завершить тест"}
              </Button>
            )}
          </div>
        </Panel>
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <PageHeader back={back} title="Тест по материалам курса"
        description="Вопросы составляются по фрагментам лекций, найденным по вашей теме. Ответы проверяются автоматически по эталону." />
      <Panel>
        <div className="space-y-5">
          <div className="space-y-1.5">
            <Label htmlFor="topic">Тема</Label>
            <Input id="topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Например: быстрая сортировка" />
          </div>
          <div className="flex flex-wrap gap-8">
            <div className="space-y-1.5">
              <Label htmlFor="cnt">Вопросов</Label>
              <Input id="cnt" type="number" min={1} max={20} value={count} className="w-24"
                onChange={(e) => setCount(Math.max(1, Math.min(20, Number(e.target.value) || 1)))} />
            </div>
            <div className="space-y-1.5">
              <span className="text-sm font-medium">Сложность</span>
              <div className="flex gap-2">
                {Object.entries(TEST_DIFFICULTY_MAP).map(([k, v]) => (
                  <Chip key={k} active={difficulty === k} onClick={() => setDifficulty(k)}>{v.label}</Chip>
                ))}
              </div>
            </div>
          </div>
          <Button disabled={topic.trim().length < 2 || generate.isPending} onClick={() => generate.mutate()}>
            {generate.isPending ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Составляем вопросы…</> : "Составить тест"}
          </Button>
        </div>
      </Panel>
    </div>
  );
}
