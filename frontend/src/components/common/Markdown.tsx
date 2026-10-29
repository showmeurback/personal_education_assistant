import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

/** Текст, сформированный языковой моделью (пояснения проверки): модель может использовать
 *  Markdown — **жирный**, списки, `код`, поэтому он отрисовывается, а не выводится символами. */
export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn("prose dark:prose-invert prose-sm max-w-none", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
