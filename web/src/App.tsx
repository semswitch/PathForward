import {
  FluentProvider,
  webDarkTheme,
  Title1,
  Subtitle2,
  Body1,
  Badge,
} from "@fluentui/react-components";
import fixtureData from "./lib/fixture.json";
import type { Fixture } from "./lib/contracts";
import { GlassBoxGraph } from "./components/GlassBoxGraph";
import { AssessmentArena } from "./components/AssessmentArena";
import { TrustConsole } from "./components/TrustConsole";
import { useStyles } from "./App.styles";

const fixture = fixtureData as unknown as Fixture;

export function App() {
  const styles = useStyles();
  const { worker } = fixture;
  return (
    <FluentProvider theme={webDarkTheme} className={styles.root}>
      <main className={styles.page}>
        <header className={styles.header}>
          <Title1 as="h1">PathForward</Title1>
          <div className={styles.intro}>
            <Body1>
              Grounded reskilling for displaced workers — Agents League @ AISF 2026 ·
              Reasoning Agents track.{" "}
            </Body1>
            <Badge appearance="tint" color="brand">synthetic data</Badge>
          </div>
          <div className={styles.row}>
            <Badge appearance="outline" role="img" aria-label={`worker ${worker.id}`}>
              {worker.id}
            </Badge>
            <Subtitle2>{worker.current_role_title}</Subtitle2>
            <Badge appearance="tint" color="informative">→ {worker.target_role}</Badge>
            {worker.accessibility_needs.map((a) => (
              <Badge key={a} appearance="tint" color="success" role="img" aria-label={a}>
                {a}
              </Badge>
            ))}
          </div>
        </header>

        <div className={styles.stack}>
          <GlassBoxGraph fixture={fixture} />
          <AssessmentArena fixture={fixture} />
          <TrustConsole fixture={fixture} />
        </div>
      </main>
    </FluentProvider>
  );
}
