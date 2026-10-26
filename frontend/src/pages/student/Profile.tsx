import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { errorMessage, meApi } from "@/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Chip, Loading, PageHeader, Panel } from "@/components/common";
import { TAGS } from "@/utils/constants";

export default function Profile() {
  const profile = useQuery({ queryKey: ["me-profile"], queryFn: meApi.profile });
  const interests = useQuery({ queryKey: ["me-interests"], queryFn: meApi.interests });
  const prefs = useQuery({ queryKey: ["me-prefs"], queryFn: meApi.preferences });
  const p = profile.data;
  return (
    <div className="max-w-2xl">
      <PageHeader title={p ? `${p.first_name} ${p.last_name}` : "Профиль"} description={p ? `Логин: ${p.login}` : undefined} />
      {p && interests.data && prefs.data ? (
        <ProfileForms about0={p.characteristic ?? ""} tags0={interests.data}
          style0={prefs.data.preferred_explanation_style ?? ""} notes0={prefs.data.notes ?? ""} />
      ) : <Loading />}
    </div>
  );
}

function ProfileForms({ about0, tags0, style0, notes0 }: { about0: string; tags0: string[]; style0: string; notes0: string }) {
  const qc = useQueryClient();
  const [about, setAbout] = useState(about0);
  const [tags, setTags] = useState<string[]>(tags0);
  const [style, setStyle] = useState(style0);
  const [notes, setNotes] = useState(notes0);

  const saved = (what: string, key: string) => () => { toast.success(`${what} сохранены`); qc.invalidateQueries({ queryKey: [key] }); qc.invalidateQueries({ queryKey: ["me-recs"] }); };
  const fail = (e: unknown) => toast.error(errorMessage(e));
  const saveAbout = useMutation({ mutationFn: () => meApi.updateCharacteristic(about), onSuccess: saved("Сведения о себе", "me-profile"), onError: fail });
  const saveTags = useMutation({ mutationFn: () => meApi.updateInterests(tags), onSuccess: saved("Интересы", "me-interests"), onError: fail });
  const savePrefs = useMutation({ mutationFn: () => meApi.updatePreferences({ preferred_explanation_style: style, notes }), onSuccess: saved("Предпочтения", "me-prefs"), onError: fail });

  return (
      <div className="space-y-4">
        <Panel title="Интересы" description="По ним подбираются рекомендованные курсы.">
          <div className="flex flex-wrap gap-2">
            {TAGS.map((t) => <Chip key={t} active={tags.includes(t)} onClick={() => setTags((x) => x.includes(t) ? x.filter((y) => y !== t) : [...x, t])}>{t}</Chip>)}
          </div>
          <Button size="sm" className="mt-4" onClick={() => saveTags.mutate()} disabled={saveTags.isPending}>Сохранить интересы</Button>
        </Panel>
        <Panel title="О себе" description="Сравнивается с описаниями курсов по смыслу — это уточняет рекомендации.">
          <Textarea rows={4} value={about} onChange={(e) => setAbout(e.target.value)} aria-label="О себе"
            placeholder="Цели, опыт, что хотите изучить" />
          <Button size="sm" className="mt-3" onClick={() => saveAbout.mutate()} disabled={saveAbout.isPending}>Сохранить</Button>
        </Panel>
        <Panel title="Как объяснять материал" description="Ассистент учитывает эти настройки во всех диалогах.">
          <div className="space-y-3">
            <div className="space-y-1.5"><Label htmlFor="st">Стиль объяснения</Label>
              <Textarea id="st" rows={3} value={style} onChange={(e) => setStyle(e.target.value)} placeholder="Например: коротко, с примерами кода" /></div>
            <div className="space-y-1.5"><Label htmlFor="nt">Заметки</Label>
              <Textarea id="nt" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Например: лучше понимаю через аналогии" /></div>
          </div>
          <Button size="sm" className="mt-3" onClick={() => savePrefs.mutate()} disabled={savePrefs.isPending}>Сохранить предпочтения</Button>
        </Panel>
      </div>
  );
}
