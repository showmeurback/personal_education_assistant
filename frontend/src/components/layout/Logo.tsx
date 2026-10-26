/** Знак приложения: два узла — квадратный (символьный) и круглый (нейросетевой), соединённые связью. */
export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect x="1" y="1" width="30" height="30" rx="8" fill="#13213f" stroke="#2a4275" />
      <rect x="6.5" y="9" width="8" height="8" rx="1.5" fill="var(--symbolic)" />
      <circle cx="21.5" cy="19" r="4.5" fill="var(--neural)" />
      <path d="M14.5 13 L17.5 16.5" stroke="#8fa3c8" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function Logo() {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark />
      <span className="font-heading text-[15px] leading-tight text-foreground">
        Ассистент
        <span className="block text-[11px] font-body text-muted-foreground tracking-normal">по обучению</span>
      </span>
    </span>
  );
}
