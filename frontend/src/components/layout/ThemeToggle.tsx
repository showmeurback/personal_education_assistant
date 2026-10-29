import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

/** Переключатель светлой и тёмной темы. Выбор сохраняется в браузере;
 *  до первого выбора тема следует настройке операционной системы. */
export function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  const dark = resolvedTheme !== "light";
  const label = dark ? "Включить светлую тему" : "Включить тёмную тему";
  return (
    <button
      type="button"
      onClick={() => setTheme(dark ? "light" : "dark")}
      className={cn("p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-surface-2 transition-colors", className)}
      aria-label={label}
      title={label}
    >
      {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
    </button>
  );
}
