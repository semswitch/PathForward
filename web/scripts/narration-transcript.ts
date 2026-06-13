/*
 * Emit a timecoded, read-along narration transcript from the CURRENT script +
 * manifest — no synthesis, no network. For reading along to tour-dry.wav.
 *
 *   npm run narration:transcript
 *
 * Output: narration-work/narration-script.md  (regenerated on every `npm run
 * narration` too, so it always matches the audio).
 */

import { mkdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { buildTourScript } from "../src/tour/script";
import { writeTranscript } from "./lib/transcript";
import type { TranscriptManifest } from "./lib/transcript";

const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const MANIFEST_PATH = join(WEB_ROOT, "src", "tour", "narration.manifest.json");
const WORK_DIR = join(WEB_ROOT, "narration-work");
const OUT = join(WORK_DIR, "narration-script.md");

const manifest = JSON.parse(
  readFileSync(MANIFEST_PATH, "utf8")
) as TranscriptManifest;
const beats = buildTourScript();
mkdirSync(WORK_DIR, { recursive: true });
writeTranscript(OUT, beats, manifest);
console.log(
  `Wrote ${OUT}\n  ${beats.length} beats, total ${(manifest.totalMs / 1000).toFixed(1)}s.`
);
