/*
 * Render a human-readable, timecoded read-along for the tour narration, synced
 * to tour-dry.wav via the manifest offsets. Shared by the synthesis pipeline
 * (generate-narration.ts, auto-emit) and the standalone narration-transcript.ts
 * so the transcript can never drift from the audio.
 */

import { writeFileSync } from "node:fs";
import { CHAPTER_LABELS } from "../../src/tour/script";
import type { TourBeat } from "../../src/tour/script";

export interface TranscriptManifestBeat {
  id: string;
  startMs: number;
  durationMs: number;
}

export interface TranscriptManifest {
  voice: string | null;
  totalMs: number;
  beats: TranscriptManifestBeat[];
}

function timecode(ms: number): string {
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function renderTranscript(
  beats: TourBeat[],
  manifest: TranscriptManifest
): string {
  const startById = new Map(manifest.beats.map((b) => [b.id, b.startMs]));
  const lines: string[] = [
    "# PathForward — Architecture Tour narration",
    "",
    `Voice ${manifest.voice ?? "?"} · total ${timecode(manifest.totalMs)} · ${beats.length} beats.`,
    "",
    "Read-along, timecoded to `tour-dry.wav` (import at 00:00.000). The plain line",
    "is the spoken narration; the indented *caption* is the on-screen text — the",
    "technical layer for judges and engineers. Skip it for a pure listen.",
    "",
  ];

  let lastChapter = "";
  for (const beat of beats) {
    if (beat.chapter !== lastChapter) {
      lines.push(`## ${CHAPTER_LABELS[beat.chapter]}`, "");
      lastChapter = beat.chapter;
    }
    const start = startById.get(beat.id);
    const tc = start === undefined ? "—" : timecode(start);
    lines.push(`**[${tc}]**  ${beat.narration}`, "");
    lines.push(`> *caption:* ${beat.caption}`, "");
  }

  return lines.join("\n") + "\n";
}

export function writeTranscript(
  path: string,
  beats: TourBeat[],
  manifest: TranscriptManifest
): void {
  writeFileSync(path, renderTranscript(beats, manifest));
}
