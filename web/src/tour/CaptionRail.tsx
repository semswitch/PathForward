import { AnimatePresence, motion } from "motion/react";

interface CaptionRailProps {
  caption: string;
  chapterLabel: string;
}

/**
 * Narration panel. Kept very translucent with NO backdrop-blur so node cards
 * behind it stay clearly visible; legibility comes from a text-shadow halo
 * (.pf-caption-text) instead of a solid or blurred box. The aria-live wrapper
 * persists across caption swaps (a live region that unmounts never announces);
 * only the inner text animates.
 */
export function CaptionRail({ caption, chapterLabel }: CaptionRailProps) {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-6 z-10 flex justify-center px-6">
      <div className="w-full max-w-2xl rounded-xl border border-line/40 bg-surface-raised/25 px-5 py-3 shadow-lg">
        <p className="pf-caption-text font-mono text-[10px] tracking-widest text-brand-300 uppercase">
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
              className="pf-caption-text text-sm leading-relaxed"
            >
              {caption}
            </motion.p>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
