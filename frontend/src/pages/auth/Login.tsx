import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuthStore, type UserRole } from "@/store/authStore";
import { authApi, errorMessage } from "@/api";
import { Logo } from "@/components/layout/Logo";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

export default function Login() {
  const [role, setRole] = useState<UserRole>("student");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const signIn = useAuthStore((s) => s.login);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const session = await authApi.login(login.trim(), password, role);
      signIn(session);
      navigate(session.role === "teacher" ? "/teacher/dashboard" : "/student/dashboard");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen bg-background flex items-center justify-center px-4 py-10">
      <ThemeToggle className="absolute right-4 top-4" />
      <div className="w-full max-w-sm">
        <Link to="/" className="flex justify-center mb-8"><Logo /></Link>
        <div className="rounded-lg bg-card border border-border p-6 sm:p-7">
          <h1 className="text-xl text-foreground">Вход</h1>
          <Tabs value={role} onValueChange={(v) => setRole(v as UserRole)} className="mt-5 mb-5">
            <TabsList className="w-full">
              <TabsTrigger value="student" className="flex-1">Студент</TabsTrigger>
              <TabsTrigger value="teacher" className="flex-1">Преподаватель</TabsTrigger>
            </TabsList>
          </Tabs>
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="login">Логин</Label>
              <Input id="login" value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Пароль</Label>
              <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
            </div>
            {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>{loading ? "Входим…" : "Войти"}</Button>
          </form>
        </div>
        <p className="text-sm text-muted-foreground text-center mt-5">
          Нет аккаунта? <Link to="/register" className="text-primary hover:underline">Зарегистрироваться</Link>
        </p>
      </div>
    </div>
  );
}
