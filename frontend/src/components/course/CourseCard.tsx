import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Course } from "@/api";
import { COURSE_TINTS, DIFFICULTY_MAP } from "@/utils/constants";
import { cn } from "@/lib/utils";

interface Props {
  course: Course;
  to: string;
  footer?: ReactNode;
  badge?: ReactNode;
}

export function CourseCard({ course, to, footer, badge }: Props) {
  const tint = COURSE_TINTS[course.id % COURSE_TINTS.length];
  const diff = DIFFICULTY_MAP[course.difficulty] ?? DIFFICULTY_MAP.intermediate;
  return (
    <div className="group flex flex-col rounded-lg bg-card border border-border hover:border-primary/50 transition-colors overflow-hidden">
      <Link to={to} className="flex-1 flex flex-col focus-visible:outline-offset-[-2px]">
        <div className="relative h-20 overflow-hidden" style={{ background: tint }}>
          <span className="absolute right-3 -bottom-5 font-heading text-[64px] leading-none text-white/10 select-none">
            {course.title.charAt(0)}
          </span>
          <div className="absolute left-4 top-3 flex gap-1.5">
            <span className={cn("rounded-md border px-2 py-0.5 text-[11px] font-medium bg-black/20", diff.color)}>{diff.label}</span>
            {badge}
          </div>
        </div>
        <div className="p-4 flex-1">
          <h3 className="font-body text-[15px] font-semibold text-foreground leading-snug line-clamp-2 group-hover:text-primary transition-colors">
            {course.title}
          </h3>
          {course.description && <p className="text-sm text-muted-foreground mt-1.5 line-clamp-2">{course.description}</p>}
          {course.tags?.length > 0 && (
            <p className="text-xs text-muted-foreground mt-3">{course.tags.slice(0, 3).join(", ")}</p>
          )}
        </div>
      </Link>
      {footer && <div className="px-4 pb-4">{footer}</div>}
    </div>
  );
}
