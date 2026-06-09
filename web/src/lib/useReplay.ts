// Replay transport: owns the clock that advances through the Director's beats.
// Pacing is identical under prefers-reduced-motion (pacing serves narration;
// motion is decoration and lives in CSS only).
import { useCallback, useEffect, useState } from "react";
import type { Beat } from "./director";

export interface ReplayState {
  beatIndex: number;
  playing: boolean;
  atEnd: boolean;
  beat: Beat | null;
}

export interface ReplayControls {
  play(): void;
  pause(): void;
  toggle(): void;
  stepForward(): void;
  stepBack(): void;
  restart(): void;
  jumpTo(beatIndex: number): void;
  skipToEnd(): void;
}

export function useReplay(beats: Beat[]): ReplayState & ReplayControls {
  const [beatIndex, setBeatIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const lastIndex = beats.length - 1;
  const atEnd = beats.length === 0 || beatIndex >= lastIndex;

  useEffect(() => {
    if (!playing || beats.length === 0) return;
    if (beatIndex >= beats.length - 1) {
      setPlaying(false);
      return;
    }
    const timer = setTimeout(() => {
      setBeatIndex((i) => Math.min(i + 1, beats.length - 1));
    }, beats[beatIndex].durationMs);
    return () => clearTimeout(timer);
  }, [playing, beatIndex, beats]);

  const clampTo = useCallback(
    (i: number) => Math.max(0, Math.min(i, Math.max(0, lastIndex))),
    [lastIndex],
  );

  const play = useCallback(() => setPlaying(true), []);
  const pause = useCallback(() => setPlaying(false), []);
  const toggle = useCallback(() => setPlaying((p) => !p), []);
  const stepForward = useCallback(
    () => setBeatIndex((i) => clampTo(i + 1)),
    [clampTo],
  );
  const stepBack = useCallback(() => setBeatIndex((i) => clampTo(i - 1)), [clampTo]);
  const restart = useCallback(() => {
    setPlaying(false);
    setBeatIndex(0);
  }, []);
  const jumpTo = useCallback((i: number) => setBeatIndex(clampTo(i)), [clampTo]);
  const skipToEnd = useCallback(() => {
    setPlaying(false);
    setBeatIndex(clampTo(Number.MAX_SAFE_INTEGER));
  }, [clampTo]);

  return {
    beatIndex,
    playing,
    atEnd,
    beat: beats[beatIndex] ?? null,
    play,
    pause,
    toggle,
    stepForward,
    stepBack,
    restart,
    jumpTo,
    skipToEnd,
  };
}
