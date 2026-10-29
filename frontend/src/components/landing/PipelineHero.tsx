/**
 * Схема каскадной гибридной проверки отчёта для главной страницы.
 * Квадраты — символьные шаги, круги — нейросетевые. Одна анимация при загрузке:
 * «сигнал» проходит по конвейеру слева направо.
 */
const nodes = [
  { x: 40, label: "Отчёт", kind: "doc" },
  { x: 135, label: "Требования", kind: "sym" },
  { x: 230, label: "Списывание", kind: "sym" },
  { x: 325, label: "Рисунки", kind: "vlm" },
  { x: 435, label: "Проверяющие ИИ", kind: "neu" },
  { x: 545, label: "Итог", kind: "sym" },
  { x: 640, label: "Решение", kind: "out" },
] as const;

export function PipelineHero() {
  return (
    <svg viewBox="0 0 680 190" className="w-full h-auto" role="img"
      aria-label="Схема проверки: отчёт, формальные требования, поиск списывания, описание рисунков, три проверяющих на основе искусственного интеллекта, итоговое правило, решение">
      <style>{`
        .pulse { offset-path: path('M40 95 L640 95'); animation: run 3.2s cubic-bezier(.6,.05,.3,.95) .4s 1 both; }
        @keyframes run { from { offset-distance: 0%; opacity: 1 } 92% { opacity: 1 } to { offset-distance: 100%; opacity: 0 } }
        @media (prefers-reduced-motion: reduce) { .pulse { display: none } }
      `}</style>
      <line x1="40" y1="95" x2="640" y2="95" stroke="var(--border)" strokeWidth="2" />
      {/* ветвление на три оценщика */}
      {[-42, 0, 42].map((dy) => (
        <path key={dy} d={`M355 95 C 390 95, 395 ${95 + dy}, 435 ${95 + dy} C 475 ${95 + dy}, 480 95, 515 95`}
          fill="none" stroke="color-mix(in srgb, var(--neural) 45%, var(--background))" strokeWidth="1.5" />
      ))}
      {/* ответвления раннего отклонения */}
      {[135, 230].map((x) => (
        <g key={x}>
          <path d={`M${x} 110 L${x} 158`} stroke="color-mix(in srgb, var(--destructive) 50%, var(--background))" strokeWidth="1.5" strokeDasharray="3 4" />
          <text x={x} y="176" textAnchor="middle" fontSize="11" fill="var(--destructive)">отклонить</text>
        </g>
      ))}
      {nodes.map((n) => {
        if (n.kind === "vlm") {
          return (
            <g key={n.label}>
              <circle cx={n.x} cy={95} r="13" fill="var(--neural)" stroke="var(--background)" strokeWidth="3" />
              <text x={n.x} y="64" textAnchor="middle" fontSize="12" fill="var(--neural)">{n.label}</text>
            </g>
          );
        }
        if (n.kind === "neu") {
          return (
            <g key={n.label}>
              {[-42, 0, 42].map((dy) => (
                <circle key={dy} cx={n.x} cy={95 + dy} r="13" fill="var(--neural)" stroke="var(--background)" strokeWidth="3" />
              ))}
              <text x={n.x} y="22" textAnchor="middle" fontSize="12" fill="var(--neural)">{n.label}</text>
            </g>
          );
        }
        const fill = n.kind === "sym" ? "var(--symbolic)" : n.kind === "doc" ? "var(--surface-2)" : "color-mix(in srgb, var(--success) 35%, var(--background))";
        const stroke = n.kind === "out" ? "var(--success)" : n.kind === "doc" ? "var(--muted-foreground)" : "var(--background)";
        return (
          <g key={n.label}>
            <rect x={n.x - 15} y="80" width="30" height="30" rx="5" fill={fill} stroke={stroke} strokeWidth="2" />
            <text x={n.x} y="64" textAnchor="middle" fontSize="12" fill="var(--foreground)">{n.label}</text>
          </g>
        );
      })}
      <circle className="pulse" r="5" fill="var(--foreground)" />
    </svg>
  );
}
