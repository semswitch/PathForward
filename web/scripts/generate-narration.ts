/*
 * Tour narration generator (build-time, runs locally — nothing here ships to
 * the browser).
 *
 *   npm run narration              # synthesize all beats, stitch, write manifest
 *   npm run narration -- --beat b-welcome   # re-synthesize one beat, re-stitch
 *   npm run narration -- --gap 500          # silence between beats (ms)
 *
 * Reads AZURE_SPEECH_KEY / AZURE_SPEECH_REGION (and optional voice/style/rate)
 * from web/.env.local or the environment.
 *
 * Outputs:
 *   narration-work/stems/NN-<beatId>.wav   dry per-beat stems (48 kHz/16-bit mono)
 *   narration-work/tour-dry.wav            stitched dry voiceover
 *   narration-work/README.md               the mixing contract (do not slide clips!)
 *   src/tour/narration.manifest.json       measured beat offsets + word timings
 *
 * The mastered mix belongs at public/narration/tour.mp3 (see the README).
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import * as sdk from "microsoft-cognitiveservices-speech-sdk";
import { buildTourScript } from "../src/tour/script";
import type { TourBeat } from "../src/tour/script";
import { writeTranscript } from "./lib/transcript";

const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const WORK_DIR = join(WEB_ROOT, "narration-work");
const STEMS_DIR = join(WORK_DIR, "stems");
const MANIFEST_PATH = join(WEB_ROOT, "src", "tour", "narration.manifest.json");

const SAMPLE_RATE = 48_000;
const BYTES_PER_MS = (SAMPLE_RATE * 2) / 1000; // 16-bit mono

// ——— env / args ———————————————————————————————————————————————————————————

function loadEnvFile(path: string): void {
  if (!existsSync(path)) return;
  for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
    const match = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/.exec(line);
    if (!match || line.trim().startsWith("#")) continue;
    const [, key, value] = match;
    if (process.env[key] === undefined || process.env[key] === "") {
      process.env[key] = value;
    }
  }
}

function argValue(flag: string): string | undefined {
  const index = process.argv.indexOf(flag);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

loadEnvFile(join(WEB_ROOT, ".env.local"));

const KEY = process.env.AZURE_SPEECH_KEY ?? "";
const REGION = process.env.AZURE_SPEECH_REGION ?? "";
const VOICE =
  argValue("--voice") ??
  process.env.AZURE_SPEECH_VOICE ??
  "en-US-AndrewMultilingualNeural";
const STYLE = process.env.AZURE_SPEECH_STYLE ?? "";
const RATE = process.env.AZURE_SPEECH_RATE ?? "";
const GAP_MS = Number(argValue("--gap") ?? 350);
const TAIL_MS = GAP_MS * 2;
const ONLY_BEAT = argValue("--beat");

if (!KEY || !REGION) {
  console.error(
    "Missing AZURE_SPEECH_KEY / AZURE_SPEECH_REGION.\n" +
      "Fill them in web/.env.local (gitignored) and re-run `npm run narration`."
  );
  process.exit(1);
}

// ——— WAV helpers ———————————————————————————————————————————————————————————

/** Extract raw PCM from a RIFF/WAVE buffer, validating the expected format. */
function extractPcm(wav: Buffer): Buffer {
  if (wav.toString("ascii", 0, 4) !== "RIFF" || wav.toString("ascii", 8, 12) !== "WAVE") {
    throw new Error("synthesis result is not a RIFF/WAVE file");
  }
  let offset = 12;
  let pcm: Buffer | null = null;
  while (offset + 8 <= wav.length) {
    const chunkId = wav.toString("ascii", offset, offset + 4);
    const chunkSize = wav.readUInt32LE(offset + 4);
    const body = offset + 8;
    if (chunkId === "fmt ") {
      const channels = wav.readUInt16LE(body + 2);
      const sampleRate = wav.readUInt32LE(body + 4);
      const bits = wav.readUInt16LE(body + 14);
      if (channels !== 1 || sampleRate !== SAMPLE_RATE || bits !== 16) {
        throw new Error(
          `unexpected WAV format ${sampleRate}Hz/${bits}bit/${channels}ch (wanted ${SAMPLE_RATE}/16/mono)`
        );
      }
    } else if (chunkId === "data") {
      pcm = wav.subarray(body, body + chunkSize);
    }
    offset = body + chunkSize + (chunkSize % 2);
  }
  if (!pcm) throw new Error("WAV data chunk not found");
  return pcm;
}

function wavHeader(pcmBytes: number): Buffer {
  const header = Buffer.alloc(44);
  header.write("RIFF", 0, "ascii");
  header.writeUInt32LE(36 + pcmBytes, 4);
  header.write("WAVE", 8, "ascii");
  header.write("fmt ", 12, "ascii");
  header.writeUInt32LE(16, 16); // fmt chunk size
  header.writeUInt16LE(1, 20); // PCM
  header.writeUInt16LE(1, 22); // mono
  header.writeUInt32LE(SAMPLE_RATE, 24);
  header.writeUInt32LE(SAMPLE_RATE * 2, 28); // byte rate
  header.writeUInt16LE(2, 32); // block align
  header.writeUInt16LE(16, 34); // bits
  header.write("data", 36, "ascii");
  header.writeUInt32LE(pcmBytes, 40);
  return header;
}

const writeWav = (path: string, pcm: Buffer) =>
  writeFileSync(path, Buffer.concat([wavHeader(pcm.length), pcm]));

const silence = (ms: number) => Buffer.alloc(Math.round(ms * BYTES_PER_MS) & ~1);

// ——— synthesis —————————————————————————————————————————————————————————————

interface WordTiming {
  t: string;
  /** Offset relative to the beat's own audio start. */
  offsetMs: number;
  durationMs: number;
}

function escapeXml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function buildSsml(narration: string): string {
  let inner = escapeXml(narration);
  if (RATE) inner = `<prosody rate="${RATE}">${inner}</prosody>`;
  if (STYLE) inner = `<mstts:express-as style="${STYLE}">${inner}</mstts:express-as>`;
  return (
    `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" ` +
    `xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">` +
    `<voice name="${VOICE}">${inner}</voice></speak>`
  );
}

function synthesizeBeat(
  beat: TourBeat
): Promise<{ pcm: Buffer; words: WordTiming[] }> {
  return new Promise((resolvePromise, rejectPromise) => {
    const config = sdk.SpeechConfig.fromSubscription(KEY, REGION);
    config.speechSynthesisOutputFormat =
      sdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm;

    // null audio config → result.audioData in memory, no local playback
    const synthesizer = new sdk.SpeechSynthesizer(config, null as never);
    const words: WordTiming[] = [];
    synthesizer.wordBoundary = (_sender, event) => {
      words.push({
        t: event.text,
        offsetMs: Math.round(event.audioOffset / 10_000),
        durationMs: Math.round(event.duration / 10_000),
      });
    };

    synthesizer.speakSsmlAsync(
      buildSsml(beat.narration),
      (result) => {
        synthesizer.close();
        if (result.reason !== sdk.ResultReason.SynthesizingAudioCompleted) {
          rejectPromise(
            new Error(`beat ${beat.id}: synthesis failed — ${result.errorDetails}`)
          );
          return;
        }
        resolvePromise({ pcm: extractPcm(Buffer.from(result.audioData)), words });
      },
      (error) => {
        synthesizer.close();
        rejectPromise(new Error(`beat ${beat.id}: ${error}`));
      }
    );
  });
}

// ——— main ———————————————————————————————————————————————————————————————————

interface Manifest {
  version: number;
  generatedAt: string | null;
  voice: string | null;
  gapMs: number;
  totalMs: number;
  beats: { id: string; startMs: number; durationMs: number }[];
  words: Record<string, WordTiming[]>;
}

const stemPath = (index: number, beatId: string) =>
  join(STEMS_DIR, `${String(index + 1).padStart(2, "0")}-${beatId}.wav`);

async function main(): Promise<void> {
  const beats = buildTourScript();
  mkdirSync(STEMS_DIR, { recursive: true });

  const previous: Manifest | null = existsSync(MANIFEST_PATH)
    ? (JSON.parse(readFileSync(MANIFEST_PATH, "utf8")) as Manifest)
    : null;

  if (ONLY_BEAT && !beats.some((b) => b.id === ONLY_BEAT)) {
    console.error(`Unknown beat id "${ONLY_BEAT}".`);
    process.exit(1);
  }

  const words: Record<string, WordTiming[]> = { ...(previous?.words ?? {}) };
  const pcmByBeat = new Map<string, Buffer>();

  for (const [index, beat] of beats.entries()) {
    const stem = stemPath(index, beat.id);
    if (ONLY_BEAT && beat.id !== ONLY_BEAT) {
      if (!existsSync(stem)) {
        console.error(
          `--beat needs every other stem on disk; missing ${stem}. Run a full pass first.`
        );
        process.exit(1);
      }
      pcmByBeat.set(beat.id, extractPcm(readFileSync(stem)));
      continue;
    }
    process.stdout.write(`synthesizing ${beat.id} … `);
    const result = await synthesizeBeat(beat);
    pcmByBeat.set(beat.id, result.pcm);
    words[beat.id] = result.words;
    writeWav(stem, result.pcm);
    console.log(`${(result.pcm.length / BYTES_PER_MS / 1000).toFixed(2)}s, ${result.words.length} word marks`);
  }

  // Stitch: beats back-to-back with GAP_MS of silence; tail pad on the last
  // beat so the finished state lingers before the clock stops.
  const segments: Buffer[] = [];
  const manifestBeats: Manifest["beats"] = [];
  let cursorMs = 0;
  for (const [index, beat] of beats.entries()) {
    const pcm = pcmByBeat.get(beat.id);
    if (!pcm) throw new Error(`missing PCM for ${beat.id}`);
    const isLast = index === beats.length - 1;
    const audioMs = pcm.length / BYTES_PER_MS;
    const durationMs = Math.round(audioMs + (isLast ? TAIL_MS : GAP_MS));
    manifestBeats.push({ id: beat.id, startMs: Math.round(cursorMs), durationMs });
    segments.push(pcm, silence(isLast ? TAIL_MS : GAP_MS));
    cursorMs += durationMs;
  }
  const totalMs = Math.round(cursorMs);
  writeWav(join(WORK_DIR, "tour-dry.wav"), Buffer.concat(segments));

  const manifest: Manifest = {
    version: 1,
    generatedAt: new Date().toISOString(),
    voice: VOICE,
    gapMs: GAP_MS,
    totalMs,
    beats: manifestBeats,
    words,
  };
  writeFileSync(MANIFEST_PATH, JSON.stringify(manifest, null, 2) + "\n");

  writeFileSync(
    join(WORK_DIR, "README.md"),
    [
      "# Tour narration — mixing contract",
      "",
      "Generated by `npm run narration`. The manifest in",
      "`src/tour/narration.manifest.json` records where every beat starts inside",
      "`tour-dry.wav`. The site re-times its visuals from that manifest, so:",
      "",
      "1. Import `tour-dry.wav` into the DAW at the very start of the timeline",
      "   (bar 1 / 00:00.000). Project rate 48 kHz.",
      "2. **Do not slide, trim, or time-stretch the voiceover.** Process it",
      "   vertically only (EQ, compression, de-essing) and lay music underneath",
      "   (sidechain/duck to taste). Any time edit desynchronizes the visuals.",
      "3. Bounce the final master, full length from 00:00.000, as MP3 (≥160 kbps)",
      "   to `web/public/narration/tour.mp3`.",
      "4. Per-beat dry stems are in `stems/` if needed for reference.",
      "5. A timecoded read-along transcript is in `narration-script.md`.",
      "",
      `Current pass: voice ${VOICE}, gap ${GAP_MS} ms, total ${(totalMs / 1000).toFixed(1)} s.`,
      "",
      "To redo one line: `npm run narration -- --beat <beat-id>` (re-stitches and",
      "rewrites the manifest — re-import tour-dry.wav afterwards).",
      "",
    ].join("\n")
  );

  try {
    writeTranscript(join(WORK_DIR, "narration-script.md"), beats, manifest);
  } catch (error) {
    console.warn(`transcript emit skipped: ${error}`);
  }

  console.log(
    `\nDone. ${beats.length} beats, ${(totalMs / 1000).toFixed(1)}s total.\n` +
      `  dry VO:   narration-work/tour-dry.wav\n` +
      `  stems:    narration-work/stems/\n` +
      `  manifest: src/tour/narration.manifest.json\n` +
      `Master to: public/narration/tour.mp3 (see narration-work/README.md)`
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
