import type { TourBeat } from "./script";

export interface NarrationManifest {
  version: number;
  generatedAt: string | null;
  voice: string | null;
  gapMs: number;
  totalMs: number;
  beats: { id: string; startMs: number; durationMs: number }[];
  words: Record<
    string,
    { t: string; offsetMs: number; durationMs: number }[]
  >;
}

export interface RetimeResult {
  beats: TourBeat[];
  /** True only when the manifest covers the authored script exactly. */
  matched: boolean;
}

/**
 * Overwrite the authored beat timings with measured narration offsets.
 * Fails safe: if the manifest is empty or doesn't match the authored beats
 * one-for-one in order (script changed since generation), the authored
 * timings are returned unchanged and the tour runs in silent mode rather
 * than desyncing from the audio.
 */
export function retimeBeats(
  beats: TourBeat[],
  manifest: NarrationManifest
): RetimeResult {
  const matched =
    manifest.beats.length === beats.length &&
    manifest.beats.every((entry, index) => entry.id === beats[index].id);

  if (!matched) {
    if (manifest.beats.length > 0) {
      console.warn(
        "narration manifest does not match the authored tour script — " +
          "running silent; re-run `npm run narration`"
      );
    }
    return { beats, matched: false };
  }

  return {
    beats: beats.map((beat, index) => ({
      ...beat,
      startMs: manifest.beats[index].startMs,
      durationMs: manifest.beats[index].durationMs,
    })),
    matched: true,
  };
}
