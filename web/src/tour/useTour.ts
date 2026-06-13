import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { TourClock } from "./clock";
import { createTimerClock } from "./clock";
import type { ChapterId, TourBeat } from "./script";
import { totalDurationMs } from "./script";

export interface TourTransport {
  beatIndex: number;
  beat: TourBeat;
  elapsedMs: number;
  totalMs: number;
  playing: boolean;
  atEnd: boolean;
  play(): void;
  pause(): void;
  toggle(): void;
  stepForward(): void;
  stepBack(): void;
  restart(): void;
  seek(ms: number): void;
  jumpToBeat(index: number): void;
  jumpToChapter(chapter: ChapterId): void;
  skipToEnd(): void;
}

export interface UseTourOptions {
  /** Injectable clock — the audio-narration piece swaps this for an audio-backed one. */
  clock?: TourClock;
  autoplay?: boolean;
}

export function useTour(
  beats: TourBeat[],
  options: UseTourOptions = {}
): TourTransport {
  const clockRef = useRef<TourClock | null>(null);
  clockRef.current ??= options.clock ?? createTimerClock();
  const autoplayRef = useRef(options.autoplay ?? false);

  const totalMs = useMemo(() => totalDurationMs(beats), [beats]);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const clock = clockRef.current;
    if (!clock) return;
    const unsubscribe = clock.subscribe(setElapsedMs);
    if (autoplayRef.current) {
      clock.play(0);
      setPlaying(true);
    }
    return () => {
      unsubscribe();
      clock.pause();
    };
  }, []);

  // Auto-pause when the script runs out.
  useEffect(() => {
    if (playing && elapsedMs >= totalMs) {
      clockRef.current?.pause();
      setPlaying(false);
    }
  }, [playing, elapsedMs, totalMs]);

  const beatIndex = useMemo(() => {
    let index = 0;
    for (let i = 0; i < beats.length; i += 1) {
      if (beats[i].startMs <= elapsedMs) index = i;
      else break;
    }
    return index;
  }, [beats, elapsedMs]);

  const clampMs = useCallback(
    (ms: number) => Math.min(Math.max(ms, 0), totalMs),
    [totalMs]
  );

  const play = useCallback(() => {
    const from = elapsedMs >= totalMs ? 0 : elapsedMs;
    clockRef.current?.play(from);
    setPlaying(true);
  }, [elapsedMs, totalMs]);

  const pause = useCallback(() => {
    clockRef.current?.pause();
    setPlaying(false);
  }, []);

  const toggle = useCallback(() => {
    if (playing) pause();
    else play();
  }, [playing, play, pause]);

  const seek = useCallback(
    (ms: number) => {
      clockRef.current?.seek(clampMs(ms));
    },
    [clampMs]
  );

  const jumpToBeat = useCallback(
    (index: number) => {
      const clamped = Math.min(Math.max(index, 0), beats.length - 1);
      seek(beats[clamped].startMs);
    },
    [beats, seek]
  );

  const stepForward = useCallback(() => {
    if (beatIndex >= beats.length - 1) seek(totalMs);
    else jumpToBeat(beatIndex + 1);
  }, [beatIndex, beats.length, jumpToBeat, seek, totalMs]);

  const stepBack = useCallback(() => {
    jumpToBeat(beatIndex - 1);
  }, [beatIndex, jumpToBeat]);

  const restart = useCallback(() => {
    seek(0);
  }, [seek]);

  const jumpToChapter = useCallback(
    (chapter: ChapterId) => {
      const index = beats.findIndex((beat) => beat.chapter === chapter);
      if (index >= 0) jumpToBeat(index);
    },
    [beats, jumpToBeat]
  );

  const skipToEnd = useCallback(() => {
    seek(totalMs);
  }, [seek, totalMs]);

  return {
    beatIndex,
    beat: beats[beatIndex],
    elapsedMs: Math.min(elapsedMs, totalMs),
    totalMs,
    playing,
    atEnd: elapsedMs >= totalMs,
    play,
    pause,
    toggle,
    stepForward,
    stepBack,
    restart,
    seek,
    jumpToBeat,
    jumpToChapter,
    skipToEnd,
  };
}
