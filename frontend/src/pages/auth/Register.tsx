import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuthStore, type UserRole } from "@/store/authStore";
import { authApi, errorMessage } from "@/api";
import { TAGS } from "@/utils/constants";
import { Chip } from "@/components/common";
import { Logo } from "@/components/layout/Logo";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

const STEPS = ["Аккаунт", "Интересы", "О себе"];

export default function Register() {
  const [role, setRole] = useState<UserRole>("student");
  const [step, setStep] = useState(0);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [interests, setInterests] = useState<string[]>([]);
  const [characteristic, setCharacteristic] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const signIn = useAuthStore((s) => s.login);

  const accountValid = firstName.trim() && lastName.trim() && login.trim().length >= 3 && password.length >= 4;

  const submit = async () => {
    setLoading(true);
    setError(null);
    try {
      const base = { login: login.trim(), password, first_name: firstName.trim(), last_name: lastName.trim() };
      const session = role === "student"
        ? await authApi.registerStudent({ ...base, interests, characteristic: characteristic.trim() || undefined })
        : await authApi.registerTeacher(base);
      signIn(session);
      navigate(session.role === "teacher" ? "/teacher/dashboard" : "/student/dashboard");
    } catch (err) {
      setError(errorMessage(err));
      setStep(0);
    } finally {
      setLoading(false);
    }
  };

  const toggle = (tag: string) =>
    setInterests((p) => (p.includes(tag) ? p.filter((t) => t !== tag) : [...p, tag]));

  return (
    <div className="relative min-h-screen bg-background flex items-center justify-center px-4 py-10">
      <ThemeToggle className="absolute right-4 top-4" />
      <div className="w-full max-w-md">
        <Link to="/" className="flex justify-center mb-8"><Logo /></Link>
        <div className="rounded-lg bg-card border border-border p-6 sm:p-7">
          <h1 className="text-xl text-foreground">Регистрация</h1>
          {role === "student" && (
            <ol className="flex gap-4 mt-3 text-xs text-muted-foreground">
              {STEPS.map((s, i) => (
                <li key={s} className={i === step ? "text-primary font-medium" : i < step ? "text-foreground" : ""}>
                  {i + 1}. {s}
                </li>
              ))}
            </ol>
          )}

          {step === 0 && (
            <div className="space-y-4 mt-5">
              <Tabs value={role} onValueChange={(v) => { setRole(v as UserRole); setStep(0); }}>
                <TabsList className="w-full">
                  <TabsTrigger value="student" className="flex-1">Студент</TabsTrigger>
                  <TabsTrigger value="teacher" className="flex-1">Преподаватель</TabsTrigger>
                </TabsList>
              </Tabs>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5"><Label htmlFor="fn">Имя</Label>
                  <Input id="fn" value={firstName} onChange={(e) => setFirstName(e.target.value)} /></div>
                <div className="space-y-1.5"><Label htmlFor="ln">Фамилия</Label>
                  <Input id="ln" value={lastName} onChange={(e) => setLastName(e.target.value)} /></div>
              </div>
              <div className="space-y-1.5"><Label htmlFor="lg">Логин</Label>
                <Input id="lg" value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" />
                <p className="text-xs text-muted-foreground">Не короче 3 символов</p></div>
              <div className="space-y-1.5"><Label htmlFor="pw">Пароль</Label>
                <Input id="pw" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
                <p className="text-xs text-muted-foreground">Не короче 4 символов</p></div>
              {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
              {role === "student" ? (
                <Button className="w-full" disabled={!accountValid} onClick={() => setStep(1)}>Далее</Button>
              ) : (
                <Button className="w-full" disabled={!accountValid || loading} onClick={submit}>
                  {loading ? "Создаём…" : "Создать аккаунт"}
                </Button>
              )}
            </div>
          )}

          {step === 1 && (
            <div className="mt-5 space-y-5">
              <p className="text-sm text-muted-foreground">Отметьте темы, которые вам интересны, — по ним система подберёт курсы.</p>
              <div className="flex flex-wrap gap-2">
                {TAGS.map((t) => <Chip key={t} active={interests.includes(t)} onClick={() => toggle(t)}>{t}</Chip>)}
              </div>
              <div className="flex gap-3">
                <Button variant="outline" className="flex-1" onClick={() => setStep(0)}>Назад</Button>
                <Button className="flex-1" onClick={() => setStep(2)}>Далее</Button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="mt-5 space-y-5">
              <div className="space-y-1.5">
                <Label htmlFor="ch">Цели и опыт (необязательно)</Label>
                <Textarea id="ch" rows={5} value={characteristic} onChange={(e) => setCharacteristic(e.target.value)}
                  placeholder="Например: хочу стать бэкенд-разработчиком, знаю основы Python, интересуют базы данных" />
                <p className="text-xs text-muted-foreground">Описание сравнивается с описаниями курсов по смыслу и уточняет рекомендации.</p>
              </div>
              <div className="flex gap-3">
                <Button variant="outline" className="flex-1" onClick={() => setStep(1)}>Назад</Button>
                <Button className="flex-1" disabled={loading} onClick={submit}>{loading ? "Создаём…" : "Создать аккаунт"}</Button>
              </div>
            </div>
          )}
        </div>
        <p className="text-sm text-muted-foreground text-center mt-5">
          Уже есть аккаунт? <Link to="/login" className="text-primary hover:underline">Войти</Link>
        </p>
      </div>
    </div>
  );
}
