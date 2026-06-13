import { describe, expect, it } from "vitest";
import type { NarrationAudio } from "./audioClock";
import { createAudioClock } from "./audioClock";

class StubAudio implements NarrationAudio {
  currentTime = 0;
  playing = false;
  private listeners = new Map<string, Set<() => void>>();

  play() {
    this.playing = true;
    this.dispatch("play");
  }
  pause() {
    this.playing = false;
    this.dispatch("pause");
  }
  addEventListener(type: string, listener: () => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)?.add(listener);
  }
  removeEventListener(type: string, listener: () => void) {
    this.listeners.get(type)?.delete(listener);
  }
  dispatch(type: string) {
    for (const listener of this.listeners.get(type) ?? []) listener();
  }
}

function setup() {
  const audio = new StubAudio();
  const clock = createAudioClock(audio);
  const seen: number[] = [];
  clock.subscribe((ms) => seen.push(ms));
  return { audio, clock, seen };
}

describe("createAudioClock", () => {
  it("play() seeks the element, starts playback, and emits", () => {
    const { audio, clock, seen } = setup();
    clock.play(5000);
    expect(audio.currentTime).toBe(5);
    expect(audio.playing).toBe(true);
    expect(seen).toContain(5000);
  });

  it("seek() sets currentTime and emits immediately in milliseconds", () => {
    const { audio, clock, seen } = setup();
    clock.seek(12_345);
    expect(audio.currentTime).toBeCloseTo(12.345);
    expect(seen[seen.length - 1]).toBeCloseTo(12_345);
  });

  it("pause() pauses the element and emits the frozen position", () => {
    const { audio, clock, seen } = setup();
    clock.play(1000);
    clock.pause();
    expect(audio.playing).toBe(false);
    expect(seen[seen.length - 1]).toBe(1000);
  });

  it("relays the element's own timeupdate events (audio is the master clock)", () => {
    const { audio, seen } = setup();
    audio.currentTime = 7.5;
    audio.dispatch("timeupdate");
    expect(seen[seen.length - 1]).toBe(7500);
  });

  it("emits on ended so the transport can auto-pause at the end", () => {
    const { audio, seen } = setup();
    audio.currentTime = 171.34;
    audio.dispatch("ended");
    expect(seen[seen.length - 1]).toBeCloseTo(171_340);
  });
});
