import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { REPORT_STATUS_MAP } from "@/utils/constants";

export function PageHeader({ title, description, actions, back }: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  back?: { to: string; label: string };
}) {
  return (
    <div className="mb-7">
      {back && (
        <Link to={back.to} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-4">
          <ArrowLeft className="w-4 h-4" /> {back.label}
        </Link>
      )}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl sm:text-[28px] leading-tight text-foreground">{title}</h1>
          {description && <p className="text-muted-foreground mt-2 max-w-2xl">{description}</p>}
        </div>
        {actions && <div className="flex gap-2 shrink-0">{actions}</div>}
      </div>
    </div>
  );
}

export function Panel({ children, className, title, description, actions }: {
  children: ReactNode;
  className?: string;
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    // min-w-0: внутри сетки панель не растягивается шириной таблицы — таблица прокручивается сама
    <section className={cn("min-w-0 rounded-lg bg-card border border-border p-5 sm:p-6", className)}>
      {(title || actions) && (
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            {title && <h2 className="font-body text-base font-semibold text-foreground">{title}</h2>}
            {description && <p className="text-sm text-muted-foreground mt-0.5">{description}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatTile({ label, value, hint, tone = "default" }: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "default" | "success" | "warning" | "danger" | "primary";
}) {
  const toneCls = {
    default: "text-foreground",
    success: "text-success",
    warning: "text-warning",
    danger: "text-destructive",
    primary: "text-primary",
  }[tone];
  return (
    <div className="rounded-lg bg-card border border-border px-5 py-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className={cn("font-heading text-2xl mt-1", toneCls)}>{value}</p>
      {hint && <p className="text-xs text-muted-foreground mt-1">{hint}</p>}
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const s = REPORT_STATUS_MAP[status] ?? { label: status, color: "bg-muted text-muted-foreground border-border", hint: "" };
  return (
    <span title={s.hint} className={cn("inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap", s.color)}>
      {s.label}
    </span>
  );
}

export function Chip({ children, className, active, onClick }: {
  children: ReactNode;
  className?: string;
  active?: boolean;
  onClick?: () => void;
}) {
  const Comp = onClick ? "button" : "span";
  return (
    <Comp
      type={onClick ? "button" : undefined}
      onClick={onClick}
      aria-pressed={onClick ? active : undefined}
      className={cn(
        "inline-flex items-center rounded-md border px-2.5 py-1 text-xs transition-colors",
        active ? "bg-primary/15 text-primary border-primary/40" : "border-border text-muted-foreground",
        onClick && !active && "hover:border-primary/40 hover:text-foreground",
        className
      )}
    >
      {children}
    </Comp>
  );
}

export function EmptyState({ icon: Icon, title, text, action }: {
  icon: React.ElementType;
  title: string;
  text?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-border px-6 py-12 text-center">
      <Icon className="w-10 h-10 text-muted-foreground/60 mx-auto mb-3" />
      <h3 className="font-body text-base font-semibold text-foreground">{title}</h3>
      {text && <p className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">{text}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Loading({ label = "Загрузка…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground py-10 justify-center">
      <Loader2 className="w-4 h-4 animate-spin" /> {label}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
      {error instanceof Error ? error.message : String(error)}
    </div>
  );
}

export function Meter({ value, max = 1, tone = "primary", markers = [] }: {
  value: number;
  max?: number;
  tone?: "primary" | "success" | "warning" | "danger" | "neural";
  markers?: { at: number; label: string }[];
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const bar = {
    primary: "bg-primary",
    success: "bg-success",
    warning: "bg-warning",
    danger: "bg-destructive",
    neural: "bg-neural",
  }[tone];
  return (
    <div className="relative h-2 rounded-full bg-surface-2 overflow-visible">
      <div className={cn("h-full rounded-full", bar)} style={{ width: `${pct}%` }} />
      {markers.map((m) => (
        <div key={m.label} className="absolute -top-1 h-4 w-px bg-foreground/60" style={{ left: `${(m.at / max) * 100}%` }} title={m.label} />
      ))}
    </div>
  );
}
