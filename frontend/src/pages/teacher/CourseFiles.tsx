import { useRef } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, Loader2, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { coursesApi, errorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { EmptyState, PageHeader } from "@/components/common";
import { formatDate } from "@/utils/constants";

export default function CourseFiles() {
  const courseId = Number(useParams().id);
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const { data = [] } = useQuery({ queryKey: ["files", courseId], queryFn: () => coursesApi.files(courseId) });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["files", courseId] }); qc.invalidateQueries({ queryKey: ["course", courseId] }); };

  const uploadM = useMutation({
    mutationFn: (files: File[]) => coursesApi.uploadFiles(courseId, files),
    onSuccess: (r) => {
      const chunks = r.indexed.reduce((s, x) => s + x.chunks, 0);
      toast.success(`Проиндексировано файлов: ${r.indexed.length}, фрагментов: ${chunks}`);
      r.errors.forEach((e) => toast.error(`${e.filename}: ${e.error}`));
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({ mutationFn: (id: number) => coursesApi.deleteFile(courseId, id), onSuccess: () => { toast.success("Файл удалён из базы знаний"); refresh(); } });

  return (
    <div className="max-w-3xl">
      <PageHeader back={{ to: `/teacher/courses/${courseId}`, label: "К курсу" }} title="Материалы курса"
        description="Файлы разбиваются на фрагменты и векторизуются — на них опираются ассистент и генератор тестов."
        actions={
          <Button onClick={() => input.current?.click()} disabled={uploadM.isPending}>
            {uploadM.isPending ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Индексация…</> : <><Upload className="w-4 h-4 mr-2" /> Загрузить</>}
          </Button>} />
      <input ref={input} type="file" multiple accept=".pdf,.docx,.txt" className="hidden"
        onChange={(e) => { const f = Array.from(e.target.files ?? []); if (f.length) uploadM.mutate(f); e.target.value = ""; }} />
      {data.length ? (
        <ul className="rounded-lg border border-border divide-y divide-border bg-card">
          {data.map((f) => (
            <li key={f.id} className="flex items-center gap-3 px-4 py-3">
              <FileText className="w-4 h-4 text-muted-foreground" />
              <span className="flex-1 min-w-0 text-sm text-foreground truncate">{f.filename}<span className="block text-xs text-muted-foreground">{formatDate(f.created_at)}</span></span>
              <button className="p-2 text-muted-foreground hover:text-foreground" aria-label="Скачать" onClick={() => coursesApi.downloadFile(courseId, f)}><Download className="w-4 h-4" /></button>
              <button className="p-2 text-muted-foreground hover:text-destructive" aria-label="Удалить"
                onClick={() => { if (window.confirm(`Удалить «${f.filename}» из материалов курса?`)) remove.mutate(f.id); }}><Trash2 className="w-4 h-4" /></button>
            </li>
          ))}
        </ul>
      ) : <EmptyState icon={FileText} title="Материалов пока нет" text="Загрузите лекции в формате PDF, DOCX или TXT." />}
    </div>
  );
}
