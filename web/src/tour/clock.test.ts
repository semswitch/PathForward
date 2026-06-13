import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createTimerClock } from "./clock";

describe("createTimerClock", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("advances elapsed time while playing", () => {
    const clock = createTimerClock(100);
    const seen: number[] = [];
    clock.subscribe((ms) => seen.push(ms));

    clock.play(0);
    expect(seen).toEqual([0]); // immediate emit on play

    vi.advanceTimersByTime(500);
    expect(seen[seen.length - 1]).toBe(500);
  });

  it("freezes on pause and resumes from the given offset", () => {
    const clock = createTimerClock(100);
    const seen: number[] = [];
    clock.subscribe((ms) => seen.push(ms));

    clock.play(0);
    vi.advanceTimersByTime(300);
    clock.pause();
    const atPause = seen[seen.length - 1];
    vi.advanceTimersByTime(1000);
    expect(seen[seen.length - 1]).toBe(atPause);

    clock.play(atPause);
    vi.advanceTimersByTime(200);
    expect(seen[seen.length - 1]).toBe(atPause + 200);
  });

  it("emits immediately on seek, even while paused", () => {
    const clock = createTimerClock(100);
    const seen: number[] = [];
    clock.subscribe((ms) => seen.push(ms));

    clock.seek(4200);
    expect(seen).toEqual([4200]);
  });

  it("stops notifying after unsubscribe", () => {
    const clock = createTimerClock(100);
    const seen: number[] = [];
    const unsubscribe = clock.subscribe((ms) => seen.push(ms));

    clock.play(0);
    vi.advanceTimersByTime(200);
    unsubscribe();
    vi.advanceTimersByTime(500);
    expect(seen[seen.length - 1]).toBe(200);
  });
});
