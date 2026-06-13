import { AnimatePresence, motion } from "motion/react";

interface CaptionRailProps {
  caption: string;
  chapterLabel: string;
}

/**
 * Narration panel. Solid backdrop so contrast holds over the glowing canvas.
 * The aria-live wrapper persists across caption swaps (a live region that
 * unmounts never announces); only the inner text animates.
 */
export function CaptionRail({ caption, chapterLabel }: CaptionRailProps) {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-6 z-10 flex justify-center px-6">
      <div className="w-full max-w-2xl rounded-xl border border-line bg-surface-raised px-5 py-3 shadow-xl">
        <p className="font-mono text-[10px] tracking-widest text-brand-300 uppercase">
          {chapterLabel}
        </p>
        <div role="status" aria-live="polite" className="mt-1 min-h-16">
          <AnimatePresence mode="wait" initial={false}>
            <motion.p
              key={caption}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
              className="text-sm leading-relaxed"
            >
              {caption}
            </motion.p>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
