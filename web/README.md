# PathForward — Web UI (Microsoft Fluent UI v9)

Skeleton for the three hero surfaces: **Glass-Box Graph**, **Assessment Arena**, **Trust Console**.
Built with `@fluentui/react-components` (Fluent UI v9), styled entirely with Griffel `makeStyles` +
design tokens (no ad-hoc CSS). Renders a real fixture exported from the offline Python run.

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
- **Here:** component structure, the data contracts (`src/lib/contracts.ts`) matching the Python
  output, a Fluent v9 layout (`FluentProvider` + `webDarkTheme`, Griffel `makeStyles`), and live
  rendering of the EMP-001 demo fixture.
- **To come (Azure layer):** swap the static fixture for live Foundry agent output; replace the
  Glass-Box edge list with an animated graph (e.g. reactflow/d3) for the hero shot; wire the Voice
  Live Oral Viva; stream eval/red-team/OTel panels into the Trust Console.

## Conventions / hardening
- **Styling is Fluent-only:** Griffel `makeStyles` + `tokens`, enforced by `@griffel/eslint-plugin`
  (longhand CSS props, top-level styles, `use`-prefixed hooks). No `*.css` files.
- **Accessibility:** `@microsoft/eslint-plugin-fluentui-jsx-a11y` lints Fluent v9 components for a11y.
- **Local port:** dev server and `vite preview` both bind to **9711** (`strictPort`).
- `fixture.json` is git-ignored (regenerate with `python scripts/export_web_fixture.py`).
