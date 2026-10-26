import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import {
  LayoutDashboard, BookOpen, GraduationCap, FileCheck2, User, TrendingUp, LogOut, Menu, X, Cpu,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Logo } from "./Logo";

const studentNav = [
  { to: "/student/dashboard", icon: LayoutDashboard, label: "Главная" },
  { to: "/student/my-courses", icon: GraduationCap, label: "Мои курсы" },
  { to: "/student/catalog", icon: BookOpen, label: "Каталог" },
  { to: "/student/progress", icon: TrendingUp, label: "Успеваемость" },
  { to: "/student/profile", icon: User, label: "Профиль" },
];

const teacherNav = [
  { to: "/teacher/dashboard", icon: LayoutDashboard, label: "Главная" },
  { to: "/teacher/courses", icon: GraduationCap, label: "Курсы" },
  { to: "/teacher/reports", icon: FileCheck2, label: "Проверка отчётов" },
  { to: "/teacher/system", icon: Cpu, label: "О системе" },
];

export function Sidebar() {
  const { role, name, logout } = useAuthStore();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const nav = role === "teacher" ? teacherNav : studentNav;

  const content = (
    <>
      <div className="flex items-center justify-between px-5 h-16 border-b border-sidebar-border">
        <Logo />
        <button className="lg:hidden p-2 text-muted-foreground" onClick={() => setOpen(false)} aria-label="Закрыть меню">
          <X className="w-5 h-5" />
        </button>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {nav.map((item) => {
          const active = location.pathname.startsWith(item.to.replace("/dashboard", "/dashboard"));
          return (
            <Link
              key={item.to}
              to={item.to}
              onClick={() => setOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors border-l-2",
                active
                  ? "bg-sidebar-accent text-foreground border-primary"
                  : "text-sidebar-foreground border-transparent hover:text-foreground hover:bg-sidebar-accent/60"
              )}
            >
              <item.icon className={cn("w-4 h-4", active && "text-primary")} />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-sidebar-border p-3">
        <div className="flex items-center gap-3 px-2 py-2">
          <div className="w-9 h-9 rounded-md bg-surface-2 flex items-center justify-center text-sm font-medium text-foreground">
            {name.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-foreground truncate">{name}</p>
            <p className="text-xs text-muted-foreground">{role === "teacher" ? "Преподаватель" : "Студент"}</p>
          </div>
          <button
            onClick={logout}
            className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-surface-2 transition-colors"
            aria-label="Выйти"
            title="Выйти"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </>
  );

  return (
    <>
      <header className="lg:hidden sticky top-0 z-30 flex items-center justify-between h-14 px-4 bg-sidebar-background border-b border-sidebar-border">
        <Logo />
        <button className="p-2 text-muted-foreground" onClick={() => setOpen(true)} aria-label="Открыть меню">
          <Menu className="w-5 h-5" />
        </button>
      </header>
      <aside className="hidden lg:flex fixed left-0 top-0 z-40 h-screen w-64 border-r border-sidebar-border bg-sidebar-background flex-col">
        {content}
      </aside>
      {open && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
          <aside className="relative w-72 max-w-[85%] h-full bg-sidebar-background border-r border-sidebar-border flex flex-col">
            {content}
          </aside>
        </div>
      )}
    </>
  );
}
