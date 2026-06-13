import { describe, expect, it, vi } from "vitest";
import { makeBaseline } from "./baseline";
import { buildTourScript, totalDurationMs } from "./script";
import type { NarrationManifest } from "./retimeBeats";
import { retimeBeats } from "./retimeBeats";

const beats = buildTourScript(makeBaseline());

function makeManifest(
  overrides: Partial<NarrationManifest> = {}
): NarrationManifest {
  // Measured timings: same beats, different offsets than authored.
  let cursor = 0;
  const manifestBeats = beats.map((beat) => {
    const entry = { id: beat.id, startMs: cursor, durationMs: 4321 };
    cursor += 4321;
    return entry;
  });
  return {
    version: 1,
    generatedAt: "2026-06-13T00:00:00Z",
    voice: "test-voice",
    gapMs: 350,
    totalMs: cursor,
    beats: manifestBeats,
    words: {},
    ...overrides,
  };
}

describe("retimeBeats", () => {
  it("applies measured timings when the manifest matches exactly", () => {
    const manifest = makeManifest();
    const result = retimeBeats(beats, manifest);
    expect(result.matched).toBe(true);
    result.beats.forEach((beat, index) => {
      expect(beat.startMs).toBe(manifest.beats[index].startMs);
      expect(beat.durationMs).toBe(4321);
      expect(beat.caption).toBe(beats[index].caption); // everything else intact
    });
    expect(totalDurationMs(result.beats)).toBe(manifest.totalMs);
  });

  it("returns authored timings unchanged for an empty (placeholder) manifest", () => {
    const result = retimeBeats(beats, makeManifest({ beats: [], totalMs: 0 }));
    expect(result.matched).toBe(false);
    expect(result.beats).toBe(beats);
  });

  it("fails safe when the script has drifted from the manifest", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const stale = makeManifest();
    stale.beats[3] = { ...stale.beats[3], id: "b-renamed-beat" };
    const result = retimeBeats(beats, stale);
    expect(result.matched).toBe(false);
    expect(result.beats).toBe(beats);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it("fails safe when beat counts differ", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const truncated = makeManifest();
    truncated.beats = truncated.beats.slice(0, 5);
    expect(retimeBeats(beats, truncated).matched).toBe(false);
    warn.mockRestore();
  });
});
