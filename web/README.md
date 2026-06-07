# PathForward — Web UI (IBM Carbon)

Skeleton for the three hero surfaces: **Glass-Box Graph**, **Assessment Arena**, **Trust Console**.
Built with `@carbon/react`. Renders a real fixture exported from the offline Python run.

## Run

```bash
# from the repo root, first export the demo fixture the UI reads:
python scripts/export_web_fixture.py        # writes web/src/lib/fixture.json

cd web
npm install
npm run dev
```

## What's here vs. to come
- **Here:** component structure, the data contracts (`src/lib/contracts.ts`) matching the Python
  output, Carbon layout, and live rendering of the EMP-001 demo fixture.
- **To come (Azure layer):** swap the static fixture for live Foundry agent output; replace the
  Glass-Box edge list with an animated graph (e.g. reactflow/d3) for the hero shot; wire the Voice
  Live Oral Viva; stream eval/red-team/OTel panels into the Trust Console.

## Notes
- Styling is Carbon tokens + a minimal `app.css` for page layout only.
- `fixture.json` is git-ignored (regenerate with `python scripts/export_web_fixture.py`).
