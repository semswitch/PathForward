import { Title1, Subtitle2, Body1, Badge } from "@fluentui/react-components";
import fixtureData from "./lib/fixture.json";
import type { Fixture } from "./lib/contracts";
import { GlassBoxGraph } from "./components/GlassBoxGraph";
import { AssessmentArena } from "./components/AssessmentArena";
import { TrustConsole } from "./components/TrustConsole";
import "./app.css";

const fixture = fixtureData as unknown as Fixture;

export function App() {
  const { worker } = fixture;
  return (
    <main className="pf-page">
      <header className="pf-panel">
        <Title1 as="h1">PathForward</Title1>
        <Body1 as="p" block className="pf-panel">
          Grounded reskilling for displaced workers — Agents League @ AISF 2026 ·
          Reasoning Agents track.{" "}
          <Badge appearance="tint" color="brand">synthetic data</Badge>
        </Body1>
        <div className="pf-row-spaced pf-panel">
          <Badge appearance="outline">{worker.id}</Badge>
          <Subtitle2>{worker.current_role_title}</Subtitle2>
          <Badge appearance="tint" color="informative">→ {worker.target_role}</Badge>
          {worker.accessibility_needs.map((a) => (
            <Badge key={a} appearance="tint" color="success">{a}</Badge>
          ))}
        </div>
      </header>

      <div className="pf-stack">
        <GlassBoxGraph fixture={fixture} />
        <AssessmentArena fixture={fixture} />
        <TrustConsole fixture={fixture} />
      </div>
    </main>
  );
}
