# PathForward — Web UI

Human-first site for the PathForward agentic system, built for creative freedom:
**Vite + React + TypeScript + Tailwind CSS v4 + Motion + React Flow (`@xyflow/react`)**.

The headline surface is the **Architecture Tour** (`/tour`): the real production flow —
Foundry Prompt Agent orchestrator, A2A specialist agents, MCP Evidence Gate / Fabric /
governed mint — drawn as a directed graph with every node carrying its real runtime name,
played back as a scripted, scrubbable tour narrating the live baseline run of 2026-06-12.

## Run

```bash
cd web
npm install
npm run dev        # dev server on http://localhost:9711
npm run lint       # ESLint (typescript-eslint strict + react-hooks + jsx-a11y)
npm run test       # Vitest (happy-dom)
npm run build      # tsc --noEmit + vite build
npm run preview    # serve the production build on http://localhost:9711
```

## Pages

- `/` — jargon-free landing for workers (in progress).
- `/tour` — the Architecture Tour: auto-plays on load; Space pauses, ←/→ step beats,
  Home/End jump, chapters are clickable, and the canvas stays free to pan/zoom.
- `/technical` — the engineering story (in progress).

## How the tour works

- `src/tour/graph.ts` — the 16-node / 19-edge inventory. Labels are exact runtime names
  (agents, MCP tools, telemetry events). Friendly wording lives in captions, never labels.
- `src/tour/baseline.ts` — typed constants from the live run evidence; the script narrates
  these numbers, so the tour cannot drift from what actually happened.
- `src/tour/script.ts` — beats keyed to cumulative `startMs`. When Azure TTS narration
  lands, measured audio offsets replace the hand-set durations — nothing downstream changes.
- `src/tour/clock.ts` — the `TourClock` seam: a timer clock today, an audio-element clock
  next.
- `src/tour/deriveTourState.ts` — pure fold of beats → React Flow nodes/edges; scrubbing
  backward re-derives exactly.
- Visual language: **agents reason (rounded, warm glow) — code notarizes (sharp, mint
  edge)**. Deterministic components are never drawn as agents.

## Narration (Azure TTS)

The tour plays silently with captions until narration is generated, then drives all
visuals from the audio (the narration is the master clock; visuals are slaved to it).

1. Fill `web/.env.local` (gitignored): `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`
   (+ optional `AZURE_SPEECH_VOICE` / `AZURE_SPEECH_STYLE` / `AZURE_SPEECH_RATE`).
2. `npm run narration` — synthesizes every beat's `narration` text, writes dry stems +
   `narration-work/tour-dry.wav`, and records measured beat offsets and word timings in
   `src/tour/narration.manifest.json`.
3. Mix/master externally per `narration-work/README.md` (lay music under the dry VO,
   **no time edits**), bounce to `web/public/narration/tour.mp3`.
4. The tour's start overlay switches to "Plays with narration" automatically when the
   manifest matches the script. Re-run `npm run narration` whenever beat text changes
   (`-- --beat <id>` redoes a single line).

Fail-safes: a stale/empty manifest or an audio load error falls back to the silent
timer-clock tour — narration can never desync the visuals.

## Conventions

- **Styling:** Tailwind v4 only — tokens in `src/index.css` under `@theme`; semantic
  light/dark tokens flip via `[data-theme="dark"]` (the tour wraps itself; the shell stays
  light). Runtime-flipping tokens must go through `@theme inline`.
- **Animation:** Motion (`motion/react`) for UI transitions; React Flow owns node/viewport
  motion; CSS keyframes (reduced-motion aware) own edge glow/flow.
- **Testing:** pure logic is fully tested (script, derive, clock, useTour with an injected
  hand-cranked clock); the React Flow canvas is never mounted in happy-dom.
- **Local port:** dev server and `vite preview` both bind to **9711** (`strictPort`).
- `src/lib/fixture.json` stays git-ignored (legacy fixture path for later live-data pieces);
  tests never import it.
