import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { errorMessage, labsApi, type Lab } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState, PageHeader } from "@/components/common";

const EMPTY = { number: 1, title: "", task: "", min_words: "" as number | "", required_sections: "" };

export default function LabsManage() {
  const courseId = Number(useParams().id);
  const qc = useQueryClient();
  const labs = useQuery({ queryKey: ["labs", courseId], queryFn: () => labsApi.list(courseId) });
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Lab | null>(null);
  const [form, setForm] = useState(EMPTY);

  const openNew = () => { setEditing(null); setForm({ ...EMPTY, number: (labs.data?.length ?? 0) + 1 }); setOpen(true); };
  const openEdit = (l: Lab) => {
    setEditing(l);
    setForm({ number: l.number, title: l.title, task: l.task, min_words: l.min_words ?? "", required_sections: l.required_sections ?? "" });
    setOpen(true);
  };
  const payload = () => ({
    number: form.number, title: form.title.trim(), task: form.task,
    min_words: form.min_words === "" ? null : Number(form.min_words),
    required_sections: form.required_sections.trim() || null,
  });
  const done = (msg: string) => () => { toast.success(msg); setOpen(false); qc.invalidateQueries({ queryKey: ["labs", courseId] }); };
  const save = useMutation({
    mutationFn: () => (editing ? labsApi.update(editing.id, payload()) : labsApi.create(courseId, payload())),
    onSuccess: done(editing ? "Лабораторная обновлена" : "Лабораторная добавлена"),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (id: number) => labsApi.remove(id),
    onSuccess: () => { toast.success("Лабораторная удалена"); qc.invalidateQueries({ queryKey: ["labs", courseId] }); },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <div className="max-w-3xl">
      <PageHeader back={{ to: `/teacher/courses/${courseId}`, label: "К курсу" }} title="Лабораторные работы"
        description="Задание и формальные требования к отчёту: по ним работают продукционные правила проверки."
        actions={<Button onClick={openNew}>Добавить</Button>} />
      {labs.data?.length ? (
        <ul className="rounded-lg border border-border divide-y divide-border bg-card">
          {labs.data.map((l) => (
            <li key={l.id} className="flex items-start gap-4 px-4 py-3.5">
              <span className="w-9 h-9 rounded-md bg-surface-2 flex items-center justify-center font-heading text-sm text-primary shrink-0">{l.number}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground">{l.title}</p>
                <p className="text-xs text-muted-foreground line-clamp-2">{l.task}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Не менее {l.min_words ?? 120} слов{l.required_sections ? `; разделы: ${l.required_sections.split(/\n|;|,/).filter((s) => s.trim()).join(", ")}` : ""}
                </p>
              </div>
              <button className="p-2 text-muted-foreground hover:text-foreground" aria-label="Изменить" onClick={() => openEdit(l)}><Pencil className="w-4 h-4" /></button>
              <button className="p-2 text-muted-foreground hover:text-destructive" aria-label="Удалить"
                onClick={() => { if (window.confirm(`Удалить «${l.title}» вместе с отчётами студентов?`)) remove.mutate(l.id); }}><Trash2 className="w-4 h-4" /></button>
            </li>
          ))}
        </ul>
      ) : <EmptyState icon={FlaskConical} title="Лабораторных пока нет" action={<Button onClick={openNew}>Добавить первую</Button>} />}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-card border-border max-w-lg">
          <DialogHeader><DialogTitle>{editing ? "Изменить лабораторную" : "Новая лабораторная"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-[90px_1fr] gap-3">
              <div className="space-y-1.5"><Label htmlFor="n">Номер</Label>
                <Input id="n" type="number" min={1} value={form.number} onChange={(e) => setForm({ ...form, number: Number(e.target.value) || 1 })} /></div>
              <div className="space-y-1.5"><Label htmlFor="ti">Название</Label>
                <Input id="ti" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
            </div>
            <div className="space-y-1.5"><Label htmlFor="ta">Задание</Label>
              <Textarea id="ta" rows={5} value={form.task} onChange={(e) => setForm({ ...form, task: e.target.value })} />
              <p className="text-xs text-muted-foreground">Ключевые понятия задания система ищет в отчёте (правило R6), а оценщики сверяют отчёт с этим текстом.</p></div>
            <div className="grid grid-cols-[140px_1fr] gap-3">
              <div className="space-y-1.5"><Label htmlFor="mw">Минимум слов</Label>
                <Input id="mw" type="number" min={0} placeholder="120" value={form.min_words}
                  onChange={(e) => setForm({ ...form, min_words: e.target.value === "" ? "" : Number(e.target.value) })} /></div>
              <div className="space-y-1.5"><Label htmlFor="rs">Обязательные разделы</Label>
                <Textarea id="rs" rows={2} placeholder={"Цель работы\nВыводы"} value={form.required_sections}
                  onChange={(e) => setForm({ ...form, required_sections: e.target.value })} /></div>
            </div>
            <Button className="w-full" disabled={!form.title.trim() || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? "Сохраняем…" : editing ? "Сохранить" : "Добавить"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
