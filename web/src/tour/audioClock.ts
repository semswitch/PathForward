import type { TourClock } from "./clock";

/**
 * Structural subset of HTMLAudioElement the clock needs — keeps the clock
 * unit-testable with a plain stub object.
 */
export interface NarrationAudio {
  currentTime: number;
  play(): Promise<void> | void;
  pause(): void;
  addEventListener(type: string, listener: () => void): void;
  removeEventListener(type: string, listener: () => void): void;
}

/**
 * TourClock backed by an audio element: the narration IS the master clock and
 * the visuals are slaved to it. `timeupdate` only fires ~4×/s, so while the
 * audio is playing a requestAnimationFrame loop emits smoother readings (for
 * the scrubber and word-level sync); events remain the source of truth for
 * pause/seek/end.
 */
export function createAudioClock(audio: NarrationAudio): TourClock {
  const listeners = new Set<(elapsedMs: number) => void>();
  let rafId: number | null = null;

  const emit = () => {
    const elapsedMs = audio.currentTime * 1000;
    for (const listener of listeners) listener(elapsedMs);
  };

  const stopRaf = () => {
    if (rafId !== null && typeof cancelAnimationFrame === "function") {
      cancelAnimationFrame(rafId);
    }
    rafId = null;
  };

  const startRaf = () => {
    if (typeof requestAnimationFrame !== "function") return;
    stopRaf();
    const tick = () => {
      emit();
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
  };

  audio.addEventListener("timeupdate", emit);
  audio.addEventListener("seeked", emit);
  audio.addEventListener("ended", () => {
    stopRaf();
    emit();
  });
  audio.addEventListener("play", startRaf);
  audio.addEventListener("pause", () => {
    stopRaf();
    emit();
  });

  return {
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    play(fromMs) {
      audio.currentTime = fromMs / 1000;
      Promise.resolve(audio.play()).catch(() => {
        // Autoplay rejection or transient load error; the page's error
        // handler owns the fallback to silent mode.
      });
      emit();
    },
    pause() {
      audio.pause();
    },
    seek(toMs) {
      audio.currentTime = toMs / 1000;
      emit();
    },
  };
}
