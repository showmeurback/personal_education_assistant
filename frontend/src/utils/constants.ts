/** Темы курсов и интересы студентов: общие предметные области и направления ИТ (тот же список на сервере). */
export const TAGS = [
  "Математика",
  "Физика",
  "Химия",
  "Биология",
  "Медицина",
  "История",
  "Право",
  "Экономика",
  "Менеджмент",
  "Психология",
  "Педагогика",
  "Филология",
  "Иностранные языки",
  "Искусство и дизайн",
  "Инженерия",
  "Электроника",
  "Программирование",
  "Алгоритмы",
  "Базы данных",
  "Сети",
  "Операционные системы",
  "Web",
  "Мобильная разработка",
  "AI/ML",
  "Безопасность",
  "DevOps",
] as const;

export const DIFFICULTY_MAP: Record<string, { label: string; color: string }> = {
  beginner: { label: "Начальный", color: "bg-success/15 text-success border-success/30" },
  intermediate: { label: "Средний", color: "bg-warning/15 text-warning border-warning/30" },
  advanced: { label: "Продвинутый", color: "bg-destructive/15 text-destructive border-destructive/30" },
};

export const TEST_DIFFICULTY_MAP: Record<string, { label: string; color: string }> = {
  easy: { label: "Лёгкий", color: "bg-success/15 text-success border-success/30" },
  medium: { label: "Средний", color: "bg-warning/15 text-warning border-warning/30" },
  hard: { label: "Сложный", color: "bg-destructive/15 text-destructive border-destructive/30" },
};

/** Статусы отчётов, включая результаты гибридной проверки. */
export const REPORT_STATUS_MAP: Record<string, { label: string; color: string; hint: string }> = {
  checking: {
    label: "Проверяется",
    color: "bg-neural/15 text-foreground border-neural/40",
    hint: "Идёт автоматическая проверка: формальные требования, поиск списывания, описание рисунков и проверка искусственным интеллектом",
  },
  pending: {
    label: "У преподавателя",
    color: "bg-primary/15 text-primary border-primary/30",
    hint: "Автоматическая проверка пройдена, ждёт решения преподавателя",
  },
  "manual-review": {
    label: "Ручная проверка",
    color: "bg-warning/15 text-warning border-warning/30",
    hint: "Автоматическая проверка не пришла к уверенному решению — его примет преподаватель",
  },
  approved: { label: "Принят", color: "bg-success/15 text-success border-success/30", hint: "Отчёт принят преподавателем" },
  "not-approved": {
    label: "Не принят",
    color: "bg-destructive/15 text-destructive border-destructive/30",
    hint: "Преподаватель отклонил отчёт",
  },
  "ai-rejected": {
    label: "Отклонён проверкой",
    color: "bg-destructive/15 text-destructive border-destructive/30",
    hint: "Автоматическая проверка выявила несоответствия — исправьте и отправьте снова",
  },
};

export const DECISION_MAP: Record<string, { label: string; color: string }> = {
  approve: { label: "Принять", color: "text-success" },
  reject: { label: "Отклонить", color: "text-destructive" },
  manual_review: { label: "Ручная проверка", color: "text-warning" },
};

export const DECIDED_BY_MAP: Record<string, string> = {
  error: "сбой проверки — передан преподавателю",
  rules: "формальные требования",
  simhash: "поиск списывания",
  judges: "проверяющие ИИ и итоговое правило",
  symbolic: "проверка по правилам",
};

export const EXAM_VERDICT_MAP: Record<string, { label: string; color: string }> = {
  correct: { label: "Верно", color: "var(--success)" },
  partial: { label: "Частично", color: "var(--chart-3)" },
  incorrect: { label: "Неверно", color: "var(--destructive)" },
};

/** Оттенки синего для обложек курсов — без случайных радужных градиентов. */
export const COURSE_TINTS = ["#1e3a7a", "#17457a", "#22377d", "#1a4d6e", "#2a3570", "#14406b"];

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value.replace(" ", "T"));
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value.replace(" ", "T"));
  return Number.isNaN(d.getTime())
    ? value
    : d.toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function sameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** День сообщения чата: «Сегодня», «Вчера» или дата (с годом, если он не текущий). */
export function messageDay(value: string | null | undefined): string {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay(d, now)) return "Сегодня";
  if (sameDay(d, yesterday)) return "Вчера";
  return d.toLocaleDateString("ru-RU", {
    day: "numeric", month: "long", ...(d.getFullYear() !== now.getFullYear() ? { year: "numeric" } : {}),
  });
}

/** Время отправки сообщения (часы и минуты в часовом поясе пользователя). */
export function messageTime(value: string): string {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

/** Полная дата и время — подсказка при наведении на время сообщения. */
export function messageTimeFull(value: string): string {
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleString("ru-RU", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
