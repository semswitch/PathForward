import { cn } from "../lib/cn";
import type { ChapterId } from "./script";
import { CHAPTER_LABELS, CHAPTER_ORDER } from "./script";

interface ChapterListProps {
  current: ChapterId;
  onJump: (chapter: ChapterId) => void;
}

export function ChapterList({ current, onJump }: ChapterListProps) {
  return (
    <nav
      aria-label="Tour chapters"
      className="absolute top-4 left-4 z-10 hidden flex-col gap-0.5 rounded-xl border border-line bg-surface-raised/90 p-2 backdrop-blur md:flex"
    >
      {CHAPTER_ORDER.map((id, index) => (
        <button
          key={id}
          type="button"
          onClick={() => onJump(id)}
          aria-current={id === current ? "step" : undefined}
          className={cn(
            "rounded-lg px-3 py-1.5 text-left text-xs transition-colors",
            id === current
              ? "bg-brand-500/15 font-medium text-brand-300"
              : "text-ink-muted hover:text-ink"
          )}
        >
          <span className="mr-2 font-mono text-[10px] tabular-nums">
            {String(index + 1).padStart(2, "0")}
          </span>
          {CHAPTER_LABELS[id]}
        </button>
      ))}
    </nav>
  );
}
