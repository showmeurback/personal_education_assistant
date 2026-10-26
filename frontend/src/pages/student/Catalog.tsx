import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Search, Sparkles } from "lucide-react";
import { coursesApi, meApi, type RecommendedCourse } from "@/api";
import { CourseCard } from "@/components/course/CourseCard";
import { Input } from "@/components/ui/input";
import { Chip, EmptyState, Loading, PageHeader } from "@/components/common";
import { DIFFICULTY_MAP, TAGS } from "@/utils/constants";

function Why({ course }: { course: RecommendedCourse }) {
  if (!course.explanation?.length) return null;
  return (
    <div className="rounded-md bg-surface/70 border border-border px-3 py-2">
      <p className="text-xs text-muted-foreground mb-1">Почему рекомендован</p>
      <ul className="text-xs text-foreground space-y-0.5">
        {course.explanation.map((e) => <li key={e}>{e}</li>)}
      </ul>
    </div>
  );
}

export default function Catalog() {
  const [tab, setTab] = useState<"rec" | "all">("rec");
  const [search, setSearch] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [diff, setDiff] = useState<string | null>(null);

  const all = useQuery({ queryKey: ["courses"], queryFn: coursesApi.list });
  const rec = useQuery({ queryKey: ["me-recs"], queryFn: meApi.recommendations });

  const filtered = useMemo(() => (all.data ?? []).filter((c) => {
    if (search && !c.title.toLowerCase().includes(search.toLowerCase())) return false;
    if (tags.length && !tags.some((t) => c.tags.includes(t))) return false;
    if (diff && c.difficulty !== diff) return false;
    return true;
  }), [all.data, search, tags, diff]);

  return (
    <div>
      <PageHeader title="Каталог курсов" description="Подборка по вашим интересам и полный список курсов." />
      <div role="tablist" className="inline-flex rounded-md border border-border bg-card p-1 mb-6">
        {([["rec", "Рекомендованные"], ["all", "Все курсы"]] as const).map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`px-4 py-1.5 rounded text-sm ${tab === k ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}>
            {label}
          </button>
        ))}
      </div>

      {tab === "rec" && (
        rec.isLoading ? <Loading /> : rec.data?.has_recommendations ? (
          <div className="space-y-8">
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {rec.data.recommended.map((c) => (
                <CourseCard key={c.id} course={c} to={`/student/courses/${c.id}`} footer={<Why course={c} />} />
              ))}
            </div>
            {rec.data.maybe_like && (
              <div>
                <h2 className="font-body text-base font-semibold text-foreground mb-3">Может заинтересовать</h2>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  <CourseCard course={rec.data.maybe_like} to={`/student/courses/${rec.data.maybe_like.id}`} footer={<Why course={rec.data.maybe_like} />} />
                </div>
              </div>
            )}
          </div>
        ) : (
          <EmptyState icon={Sparkles} title="Пока нечего порекомендовать"
            text="Отметьте интересы и опишите свои цели в профиле — подборка появится здесь."
            action={<Link to="/student/profile" className="text-primary hover:underline text-sm">Перейти в профиль</Link>} />
        )
      )}

      {tab === "all" && (
        <div className="space-y-5">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input placeholder="Поиск по названию" value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" aria-label="Поиск курсов" />
          </div>
          <div className="flex flex-wrap gap-2">
            {TAGS.map((t) => <Chip key={t} active={tags.includes(t)} onClick={() => setTags((p) => p.includes(t) ? p.filter((x) => x !== t) : [...p, t])}>{t}</Chip>)}
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(DIFFICULTY_MAP).map(([k, v]) => (
              <Chip key={k} active={diff === k} onClick={() => setDiff(diff === k ? null : k)}>{v.label}</Chip>
            ))}
          </div>
          {all.isLoading ? <Loading /> : filtered.length ? (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filtered.map((c) => (
                <CourseCard key={c.id} course={c} to={`/student/courses/${c.id}`}
                  badge={c.enrolled ? <span className="rounded-md border border-success/40 bg-black/20 px-2 py-0.5 text-[11px] text-success">Вы записаны</span> : undefined} />
              ))}
            </div>
          ) : <p className="text-muted-foreground text-center py-12">Ничего не найдено — измените фильтры.</p>}
        </div>
      )}
    </div>
  );
}
