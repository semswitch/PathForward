/*
 * The tour's clock seam. The timer clock drives v1; the voice-narration piece
 * replaces it with an HTMLAudioElement-backed implementation of the SAME
 * interface (timeupdate → listener, play/pause/currentTime → play/pause/seek),
 * so nothing downstream changes when audio lands.
 */

export interface TourClock {
  /** Listener receives elapsed milliseconds. Returns an unsubscribe function. */
  subscribe(listener: (elapsedMs: number) => void): () => void;
  play(fromMs: number): void;
  pause(): void;
  seek(toMs: number): void;
}

export function createTimerClock(tickMs = 100): TourClock {
  const listeners = new Set<(elapsedMs: number) => void>();
  let elapsed = 0;
  let intervalId: ReturnType<typeof setInterval> | null = null;

  // Fixed-step accumulation (not wall-clock deltas): deterministic under fake
  // timers, and millisecond drift is irrelevant at caption granularity.
  const emit = () => {
    for (const listener of listeners) listener(elapsed);
  };

  return {
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    play(fromMs) {
      elapsed = fromMs;
      if (intervalId !== null) clearInterval(intervalId);
      intervalId = setInterval(() => {
        elapsed += tickMs;
        emit();
      }, tickMs);
      emit();
    },
    pause() {
      if (intervalId !== null) {
        clearInterval(intervalId);
        intervalId = null;
      }
    },
    seek(toMs) {
      elapsed = toMs;
      emit();
    },
  };
}
