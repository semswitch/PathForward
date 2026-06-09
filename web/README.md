# PathForward — Web UI (Microsoft Fluent UI v9)

The **Reasoning Theater**: an auto-playing, Loom-recordable replay of the multi-agent run.
A Demo Director (`src/lib/director.ts`) converts the fixture's transcript into timed beats; the
replay hook (`src/lib/useReplay.ts`) plays them while the **Agent Stage** rail lights up the
active agent (rounded brand chips = LLM reasoning agents; sharp monochrome chips = deterministic
code: Evidence Gate and Mint — "agents reason, code notarizes"). Surfaces: **Glass-Box Graph**,
**Curator Panel**, **Assessment Arena** (reject → regenerate, struck attempts stay visible),
**Plan & Program Insights**, **Trust Console** (causal-spine pulse at mint). A sticky transport
bar offers play/pause/step/restart/skip, a chapter scrubber, and the fixture-provenance badge
(`offline rehearsal` vs `live foundry replay`).
Built with `@fluentui/react-components` (Fluent UI v9), styled entirely with Griffel `makeStyles` +
design tokens (no ad-hoc CSS). Renders a real fixture exported from the offline Python run
(or `--live` for the real Foundry run). Replay pacing is identical under
`prefers-reduced-motion`; only the decorative motion is disabled.

## Run

```bash
# from the repo root, first export the demo fixture the UI reads:
python scripts/export_web_fixture.py        # writes web/src/lib/fixture.json

cd web
npm install
npm run dev        # dev server on http://localhost:9711
npm run lint       # ESLint (Griffel + Fluent v9 a11y + typescript-eslint)
npm run build      # tsc --noEmit + vite build
npm run preview    # serve the production build on http://localhost:9711
```

## What's here vs. to come
- **Here:** the replay engine (director → visible-state → hook, all unit-tested with a fixture
  factory in `src/lib/testFixture.ts` so pure-logic tests never depend on the gitignored
  `fixture.json`), the Agent Stage + transport bar, beat-gated rendering of all five panels, the
  data contracts (`src/lib/contracts.ts`) matching the Python output, and rendering of the
  EMP-001 demo fixture (including the previously unrendered curator decision, critic reviews,
  plan, and program insights).
- **To come:** a Worker View tab (the product as EMP-001 would see it), the Bluff-vs-Grounded
  closing diptych, per-beat pacing from real OTel span timings, an SVG causal-spine connector
  overlay, live Foundry streaming instead of fixture replay, the Voice Live Oral Viva.

## Conventions / hardening
- **Styling is Fluent-only:** Griffel `makeStyles` + `tokens`, enforced by `@griffel/eslint-plugin`
  (longhand CSS props, top-level styles, `use`-prefixed hooks). No `*.css` files.
- **Accessibility:** `@microsoft/eslint-plugin-fluentui-jsx-a11y` lints Fluent v9 components for a11y.
- **Local port:** dev server and `vite preview` both bind to **9711** (`strictPort`).
- `fixture.json` is git-ignored (regenerate with `python scripts/export_web_fixture.py`).
