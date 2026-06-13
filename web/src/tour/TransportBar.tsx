import type { TourTransport } from "./useTour";

export type TransportControls = Pick<
  TourTransport,
  | "playing"
  | "atEnd"
  | "elapsedMs"
  | "totalMs"
  | "toggle"
  | "stepBack"
  | "stepForward"
  | "restart"
  | "skipToEnd"
  | "seek"
>;

interface TransportBarProps {
  transport: TransportControls;
  chapterLabel: string;
}

function formatMs(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

const BUTTON_CLASSES =
  "flex h-8 w-8 items-center justify-center rounded-full border border-line text-sm text-ink-muted transition-colors hover:border-brand-400 hover:text-ink";

export function TransportBar({ transport, chapterLabel }: TransportBarProps) {
  const {
    playing,
    elapsedMs,
    totalMs,
    toggle,
    stepBack,
    stepForward,
    restart,
    skipToEnd,
    seek,
  } = transport;

  return (
    <div className="flex items-center gap-3 border-t border-line bg-surface-raised/95 px-4 py-3">
      <button type="button" aria-label="Restart" onClick={restart} className={BUTTON_CLASSES}>
        ↺
      </button>
      <button type="button" aria-label="Step back" onClick={stepBack} className={BUTTON_CLASSES}>
        ‹
      </button>
      <button
        type="button"
        aria-label={playing ? "Pause" : "Play"}
        onClick={toggle}
        className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-500 text-sm font-semibold text-white transition-colors hover:bg-brand-400"
      >
        {playing ? "❚❚" : "▶"}
      </button>
      <button type="button" aria-label="Step forward" onClick={stepForward} className={BUTTON_CLASSES}>
        ›
      </button>
      <button type="button" aria-label="Skip to end" onClick={skipToEnd} className={BUTTON_CLASSES}>
        »
      </button>
      <span className="ml-1 font-mono text-[11px] text-ink-muted tabular-nums">
        {formatMs(elapsedMs)} / {formatMs(totalMs)}
      </span>
      <input
        type="range"
        min={0}
        max={totalMs}
        step={100}
        value={elapsedMs}
        onChange={(event) => seek(Number(event.target.value))}
        aria-label="Tour position"
        aria-valuetext={`${formatMs(elapsedMs)} — ${chapterLabel}`}
        className="min-w-0 flex-1 accent-brand-400"
      />
      <span className="hidden font-mono text-[10px] tracking-widest text-brand-300 uppercase sm:block">
        {chapterLabel}
      </span>
    </div>
  );
}
