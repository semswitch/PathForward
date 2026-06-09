import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useReplay } from "./useReplay";
import { buildBeats } from "./director";
import { makeFixture } from "./testFixture";

describe("useReplay", () => {
  const beats = buildBeats(makeFixture());

  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("starts paused at beat 0", () => {
    const { result } = renderHook(() => useReplay(beats));
    expect(result.current.beatIndex).toBe(0);
    expect(result.current.playing).toBe(false);
    expect(result.current.beat).toEqual(beats[0]);
  });

  it("advances after the current beat's duration while playing", () => {
    const { result } = renderHook(() => useReplay(beats));
    act(() => result.current.play());
    act(() => {
      vi.advanceTimersByTime(beats[0].durationMs);
    });
    expect(result.current.beatIndex).toBe(1);
    act(() => {
      vi.advanceTimersByTime(beats[1].durationMs);
    });
    expect(result.current.beatIndex).toBe(2);
  });

  it("pause freezes the index", () => {
    const { result } = renderHook(() => useReplay(beats));
    act(() => result.current.play());
    act(() => result.current.pause());
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(result.current.beatIndex).toBe(0);
  });

  it("step and jump clamp to the beat range", () => {
    const { result } = renderHook(() => useReplay(beats));
    act(() => result.current.stepBack());
    expect(result.current.beatIndex).toBe(0);
    act(() => result.current.jumpTo(9999));
    expect(result.current.beatIndex).toBe(beats.length - 1);
    act(() => result.current.stepForward());
    expect(result.current.beatIndex).toBe(beats.length - 1);
    act(() => result.current.jumpTo(-5));
    expect(result.current.beatIndex).toBe(0);
  });

  it("auto-pauses at the final beat", () => {
    const { result } = renderHook(() => useReplay(beats));
    act(() => result.current.jumpTo(beats.length - 2));
    act(() => result.current.play());
    act(() => {
      vi.advanceTimersByTime(beats[beats.length - 2].durationMs);
    });
    expect(result.current.beatIndex).toBe(beats.length - 1);
    expect(result.current.atEnd).toBe(true);
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(result.current.playing).toBe(false);
    expect(result.current.beatIndex).toBe(beats.length - 1);
  });

  it("restart returns to beat 0 paused; skipToEnd lands on the last beat", () => {
    const { result } = renderHook(() => useReplay(beats));
    act(() => result.current.skipToEnd());
    expect(result.current.beatIndex).toBe(beats.length - 1);
    expect(result.current.playing).toBe(false);
    act(() => result.current.restart());
    expect(result.current.beatIndex).toBe(0);
    expect(result.current.playing).toBe(false);
  });
});
