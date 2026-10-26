/**
 * Схема каскадной гибридной проверки отчёта для главной страницы.
 * Квадраты — символьные шаги, круги — нейросетевые. Одна анимация при загрузке:
 * «сигнал» проходит по конвейеру слева направо.
 */
const nodes = [
  { x: 40, label: "Отчёт", kind: "doc" },
  { x: 135, label: "Правила", kind: "sym" },
  { x: 230, label: "SimHash", kind: "sym" },
  { x: 325, label: "Рисунки", kind: "vlm" },
  { x: 435, label: "Оценщики", kind: "neu" },
  { x: 545, label: "Арбитр", kind: "sym" },
  { x: 640, label: "Решение", kind: "out" },
] as const;

export function PipelineHero() {
  return (
    <svg viewBox="0 0 680 190" className="w-full h-auto" role="img"
      aria-label="Схема проверки: отчёт, продукционные правила, фильтр SimHash, описание рисунков моделью зрения, три языковых оценщика на разных моделях, символьный арбитр, решение">
      <style>{`
        .pulse { offset-path: path('M40 95 L640 95'); animation: run 3.2s cubic-bezier(.6,.05,.3,.95) .4s 1 both; }
        @keyframes run { from { offset-distance: 0%; opacity: 1 } 92% { opacity: 1 } to { offset-distance: 100%; opacity: 0 } }
        @media (prefers-reduced-motion: reduce) { .pulse { display: none } }
      `}</style>
      <line x1="40" y1="95" x2="640" y2="95" stroke="#213560" strokeWidth="2" />
      {/* ветвление на три оценщика */}
      {[-42, 0, 42].map((dy) => (
        <path key={dy} d={`M355 95 C 390 95, 395 ${95 + dy}, 435 ${95 + dy} C 475 ${95 + dy}, 480 95, 515 95`}
          fill="none" stroke="#2c2f6b" strokeWidth="1.5" />
      ))}
      {/* ответвления раннего отклонения */}
      {[135, 230].map((x) => (
        <g key={x}>
          <path d={`M${x} 110 L${x} 158`} stroke="#5a2a3d" strokeWidth="1.5" strokeDasharray="3 4" />
          <text x={x} y="176" textAnchor="middle" fontSize="11" fill="#c86a7c">отклонить</text>
        </g>
      ))}
      {nodes.map((n) => {
        if (n.kind === "vlm") {
          return (
            <g key={n.label}>
              <circle cx={n.x} cy={95} r="13" fill="var(--neural)" stroke="#0a1328" strokeWidth="3" />
              <text x={n.x} y="64" textAnchor="middle" fontSize="12" fill="#c9b8ff">{n.label}</text>
            </g>
          );
        }
        if (n.kind === "neu") {
          return (
            <g key={n.label}>
              {[-42, 0, 42].map((dy) => (
                <circle key={dy} cx={n.x} cy={95 + dy} r="13" fill="var(--neural)" stroke="#0a1328" strokeWidth="3" />
              ))}
              <text x={n.x} y="22" textAnchor="middle" fontSize="12" fill="#c9b8ff">{n.label}</text>
            </g>
          );
        }
        const fill = n.kind === "sym" ? "var(--symbolic)" : n.kind === "doc" ? "#1a2b50" : "#1d4f43";
        const stroke = n.kind === "out" ? "#2ebd85" : n.kind === "doc" ? "#3a5799" : "#0a1328";
        return (
          <g key={n.label}>
            <rect x={n.x - 15} y="80" width="30" height="30" rx="5" fill={fill} stroke={stroke} strokeWidth="2" />
            <text x={n.x} y="64" textAnchor="middle" fontSize="12" fill="#b8c6e3">{n.label}</text>
          </g>
        );
      })}
      <circle className="pulse" r="5" fill="#ffffff" />
    </svg>
  );
}
