import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { coursesApi, errorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Chip, Loading, PageHeader, Panel } from "@/components/common";
import { DIFFICULTY_MAP, TAGS } from "@/utils/constants";

export default function CourseEdit() {
  const { id } = useParams();
  const courseId = id ? Number(id) : null;
  const course = useQuery({ queryKey: ["course", courseId], queryFn: () => coursesApi.get(courseId!), enabled: !!courseId });
  if (courseId && !course.data) return <Loading />;
  const c = course.data;
  return (
    <CourseForm key={courseId ?? "new"} courseId={courseId}
      initial={{ title: c?.title ?? "", description: c?.description ?? "", difficulty: c?.difficulty ?? "intermediate",
        tags: c?.tags ?? [], exam: c?.exam_questions ?? "" }} />
  );
}

function CourseForm({ courseId, initial }: {
  courseId: number | null;
  initial: { title: string; description: string; difficulty: string; tags: string[]; exam: string };
}) {
  const isNew = courseId == null;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [title, setTitle] = useState(initial.title);
  const [description, setDescription] = useState(initial.description);
  const [difficulty, setDifficulty] = useState(initial.difficulty);
  const [tags, setTags] = useState<string[]>(initial.tags);
  const [exam, setExam] = useState(initial.exam);

  const save = useMutation({
    mutationFn: async () => {
      const data = { title: title.trim(), description, difficulty, tags, exam_questions: exam };
      if (isNew) return (await coursesApi.create(data)).course_id;
      await coursesApi.update(courseId!, data);
      return courseId!;
    },
    onSuccess: (cid) => {
      toast.success(isNew ? "Курс создан — загрузите материалы и добавьте лабораторные" : "Изменения сохранены");
      qc.invalidateQueries({ queryKey: ["t-courses"] });
      qc.invalidateQueries({ queryKey: ["course", cid] });
      navigate(`/teacher/courses/${cid}`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <div className="max-w-3xl">
      <PageHeader back={{ to: isNew ? "/teacher/courses" : `/teacher/courses/${courseId}`, label: isNew ? "Курсы" : "К курсу" }}
        title={isNew ? "Новый курс" : "Редактирование курса"} />
      <Panel>
        <div className="space-y-5">
          <div className="space-y-1.5"><Label htmlFor="t">Название</Label>
            <Input id="t" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
          <div className="space-y-1.5"><Label htmlFor="d">Описание</Label>
            <Textarea id="d" rows={4} value={description} onChange={(e) => setDescription(e.target.value)} />
            <p className="text-xs text-muted-foreground">Описание используется для смысловых рекомендаций — опишите, чему научится студент.</p></div>
          <div className="space-y-1.5"><span className="text-sm font-medium">Сложность</span>
            <div className="flex gap-2">{Object.entries(DIFFICULTY_MAP).map(([k, v]) => <Chip key={k} active={difficulty === k} onClick={() => setDifficulty(k)}>{v.label}</Chip>)}</div></div>
          <div className="space-y-1.5"><span className="text-sm font-medium">Теги</span>
            <div className="flex flex-wrap gap-2">{TAGS.map((t) => <Chip key={t} active={tags.includes(t)} onClick={() => setTags((p) => p.includes(t) ? p.filter((x) => x !== t) : [...p, t])}>{t}</Chip>)}</div></div>
          <div className="space-y-1.5"><Label htmlFor="e">Экзаменационные вопросы</Label>
            <Textarea id="e" rows={6} value={exam} onChange={(e) => setExam(e.target.value)}
              placeholder={"1. Что такое нормализация отношений?\n2. Чем отличается INNER JOIN от LEFT JOIN?"} />
            <p className="text-xs text-muted-foreground">По одному вопросу на строку (с вопросительным знаком). Если вопросов меньше, чем выбрал студент, недостающие сгенерирует модель по этому тексту.</p></div>
          <Button onClick={() => save.mutate()} disabled={!title.trim() || save.isPending}>{save.isPending ? "Сохраняем…" : isNew ? "Создать курс" : "Сохранить изменения"}</Button>
        </div>
      </Panel>
    </div>
  );
}
