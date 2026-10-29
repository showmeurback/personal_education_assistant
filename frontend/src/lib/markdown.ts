/** Тот же текст одной строкой без разметки — для кратких превью. */
export function plainText(md: string): string {
  return md
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/[*_`#>]+/g, "")
    .replace(/^\s*(\d+\.|[-•])\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}
