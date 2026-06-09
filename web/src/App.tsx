import { useEffect, useMemo, useRef } from "react";
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
import { buildBeats, MAX_ATTEMPTS, type ChapterId } from "./lib/director";
import { useReplay } from "./lib/useReplay";
import { deriveVisibleState } from "./lib/visibleState";
import { AgentStage } from "./components/AgentStage";
import { TransportBar } from "./components/TransportBar";
import { GlassBoxGraph } from "./components/GlassBoxGraph";
import { CuratorPanel } from "./components/CuratorPanel";
import { AssessmentArena } from "./components/AssessmentArena";
import { PlanInsightsCard } from "./components/PlanInsightsCard";
import { TrustConsole } from "./components/TrustConsole";
import { useStyles } from "./App.styles";

const fixture = fixtureData as unknown as Fixture;

export function App() {
  const styles = useStyles();
  const { worker } = fixture;

  const beats = useMemo(() => buildBeats(fixture), []);
  const replay = useReplay(beats);
  const visible = useMemo(
    () => deriveVisibleState(fixture, beats, replay.beatIndex),
    [beats, replay.beatIndex],
  );

  const graphRef = useRef<HTMLDivElement>(null);
  const curatorRef = useRef<HTMLDivElement>(null);
  const loopRef = useRef<HTMLDivElement>(null);
  const planRef = useRef<HTMLDivElement>(null);
  const trustRef = useRef<HTMLDivElement>(null);
  const chapterRefs: Record<ChapterId, React.RefObject<HTMLDivElement | null>> = useMemo(
    () => ({
      graph: graphRef,
      curator: curatorRef,
      loop: loopRef,
      decision: trustRef,
      plan: planRef,
      trust: trustRef,
    }),
    [],
  );

  // While playing, keep the active chapter's card in view (decoration only:
  // smooth scrolling is skipped under prefers-reduced-motion).
  useEffect(() => {
    if (!replay.playing) return;
    const chapter = beats[replay.beatIndex]?.chapter;
    if (!chapter) return;
    const motionOk = !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    chapterRefs[chapter].current?.scrollIntoView?.({
      behavior: motionOk ? "smooth" : "auto",
      block: "nearest",
    });
  }, [replay.playing, replay.beatIndex, beats, chapterRefs]);

  const loopBeat = replay.beat?.chapter === "loop" ? replay.beat : null;

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

        <AgentStage
          activeActor={replay.beat?.actor ?? null}
          attempt={loopBeat?.attempt}
          maxAttempts={MAX_ATTEMPTS}
          loopStatus={fixture.loop.status}
        />

        <div role="status" aria-live="polite" className={styles.srOnly}>
          {replay.beat?.caption ?? ""}
        </div>

        <div className={styles.stack}>
          <div ref={graphRef}>
            <GlassBoxGraph fixture={fixture} visible={visible.glassbox} />
          </div>
          <div ref={curatorRef}>
            <CuratorPanel fixture={fixture} visible={visible.curator} />
          </div>
          <div ref={loopRef}>
            <AssessmentArena fixture={fixture} visible={visible.arena} />
          </div>
          <div ref={planRef}>
            <PlanInsightsCard
              fixture={fixture}
              visible={{ plan: visible.plan, insights: visible.insights }}
            />
          </div>
          <div ref={trustRef}>
            <TrustConsole fixture={fixture} visible={visible.trust} />
          </div>
        </div>

        <TransportBar replay={replay} beats={beats} provenanceMode={fixture.provenance.mode} />
      </main>
    </FluentProvider>
  );
}
