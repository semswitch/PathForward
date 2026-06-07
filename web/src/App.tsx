import { Theme, Stack, Tag, Heading, Section } from "@carbon/react";
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
    <Theme theme="g100">
      <main className="pf-page">
        <Section>
          <Heading>PathForward</Heading>
          <p className="pf-panel">
            Grounded reskilling for displaced workers — Agents League @ AISF 2026 ·
            Reasoning Agents track. <Tag type="purple">synthetic data</Tag>
          </p>
          <div className="pf-row-spaced pf-panel">
            <Tag type="cool-gray">{worker.id}</Tag>
            <span>{worker.current_role_title}</span>
            <Tag type="blue">→ {worker.target_role}</Tag>
            {worker.accessibility_needs.map((a) => (
              <Tag key={a} type="teal">{a}</Tag>
            ))}
          </div>
        </Section>

        <Stack gap={6}>
          <GlassBoxGraph fixture={fixture} />
          <AssessmentArena fixture={fixture} />
          <TrustConsole fixture={fixture} />
        </Stack>
      </main>
    </Theme>
  );
}
