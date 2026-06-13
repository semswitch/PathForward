import { describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";
import type { TourClock } from "./clock";
import { makeBaseline } from "./baseline";
import { buildTourScript, totalDurationMs } from "./script";
import { useTour } from "./useTour";

/**
 * Hand-cranked clock implementing the TourClock seam — the same contract the
 * future audio-backed clock will implement. Driving useTour entirely through
 * it is the proof that the audio swap needs no useTour changes.
 */
class TestClock implements TourClock {
  elapsed = 0;
  running = false;
  private listeners = new Set<(ms: number) => void>();

  subscribe(listener: (ms: number) => void) {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }
  play(fromMs: number) {
    this.elapsed = fromMs;
    this.running = true;
    this.emit();
  }
  pause() {
    this.running = false;
  }
  seek(toMs: number) {
    this.elapsed = toMs;
    this.emit();
  }
  tick(ms: number) {
    this.elapsed += ms;
    this.emit();
  }
  private emit() {
    for (const listener of this.listeners) listener(this.elapsed);
  }
}

const beats = buildTourScript(makeBaseline());
const totalMs = totalDurationMs(beats);

function setup() {
  const clock = new TestClock();
  const hook = renderHook(() => useTour(beats, { clock }));
  return { clock, hook };
}

describe("useTour", () => {
  it("flips beatIndex exactly at startMs boundaries", () => {
    const { clock, hook } = setup();
    expect(hook.result.current.beatIndex).toBe(0);

    act(() => clock.seek(beats[1].startMs - 1));
    expect(hook.result.current.beatIndex).toBe(0);

    act(() => clock.seek(beats[1].startMs));
    expect(hook.result.current.beatIndex).toBe(1);

    act(() => clock.seek(beats[2].startMs));
    expect(hook.result.current.beatIndex).toBe(2);
  });

  it("tracks playing state through play/pause/toggle", () => {
    const { clock, hook } = setup();
    expect(hook.result.current.playing).toBe(false);

    act(() => hook.result.current.play());
    expect(hook.result.current.playing).toBe(true);
    expect(clock.running).toBe(true);

    act(() => hook.result.current.toggle());
    expect(hook.result.current.playing).toBe(false);
    expect(clock.running).toBe(false);
  });

  it("steps forward and back along beat boundaries", () => {
    const { hook } = setup();

    act(() => hook.result.current.stepForward());
    expect(hook.result.current.beatIndex).toBe(1);
    expect(hook.result.current.elapsedMs).toBe(beats[1].startMs);

    act(() => hook.result.current.stepForward());
    expect(hook.result.current.beatIndex).toBe(2);

    act(() => hook.result.current.stepBack());
    expect(hook.result.current.beatIndex).toBe(1);

    act(() => hook.result.current.stepBack());
    act(() => hook.result.current.stepBack()); // clamps at the first beat
    expect(hook.result.current.beatIndex).toBe(0);
  });

  it("jumps to a chapter's first beat", () => {
    const { hook } = setup();
    act(() => hook.result.current.jumpToChapter("abstain"));
    const index = hook.result.current.beatIndex;
    expect(beats[index].chapter).toBe("abstain");
    expect(beats[index - 1].chapter).not.toBe("abstain");
  });

  it("auto-pauses at the end of the script", () => {
    const { clock, hook } = setup();
    act(() => hook.result.current.play());
    act(() => clock.tick(totalMs + 500));
    expect(hook.result.current.playing).toBe(false);
    expect(hook.result.current.atEnd).toBe(true);
    expect(hook.result.current.beatIndex).toBe(beats.length - 1);
    expect(hook.result.current.elapsedMs).toBe(totalMs); // display clamp
  });

  it("replays from the start when play() is called at the end", () => {
    const { clock, hook } = setup();
    act(() => hook.result.current.skipToEnd());
    expect(hook.result.current.atEnd).toBe(true);

    act(() => hook.result.current.play());
    expect(clock.elapsed).toBe(0);
    expect(hook.result.current.beatIndex).toBe(0);
    expect(hook.result.current.playing).toBe(true);
  });

  it("clamps seeks into [0, totalMs]", () => {
    const { clock, hook } = setup();
    act(() => hook.result.current.seek(-500));
    expect(clock.elapsed).toBe(0);
    act(() => hook.result.current.seek(totalMs + 9999));
    expect(clock.elapsed).toBe(totalMs);
  });

  it("pauses the clock on unmount", () => {
    const { clock, hook } = setup();
    act(() => hook.result.current.play());
    expect(clock.running).toBe(true);
    hook.unmount();
    expect(clock.running).toBe(false);
  });
});
