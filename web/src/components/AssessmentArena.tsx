// Adversarial Assessment Arena (Fluent UI v9 + Griffel).
// Replays the Generator -> Critic -> Evidence Gate transcript attempt by
// attempt: the stem reveals, the Critic posts its advisory view, the five
// deterministic criteria land staggered, and the verdict strikes or passes.
// Rejected attempts stay on screen, dimmed and struck — evidence of rigor.
import {
  Card,
  Badge,
  Subtitle1,
  Body1,
  Caption1,
  Text,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
  mergeClasses,
} from "@fluentui/react-components";
import type { CriticReview, Fixture, LoopResult } from "../lib/contracts";
import type { VisibleState } from "../lib/visibleState";
import { useStyles } from "./AssessmentArena.styles";
import { CRITERIA_DELAYS, useRevealStyles } from "./reveal.styles";

type TranscriptEntry = LoopResult["transcript"][number];

export interface AssessmentArenaProps {
  fixture: Fixture;
  visible: VisibleState["arena"];
}

function CriticRow({ critic }: { critic: CriticReview }) {
  const styles = useStyles();
  return (
    <div className={styles.row}>
      <Badge
        appearance="tint"
        color={critic.recommendation === "pass" ? "success" : "warning"}
        role="img"
        aria-label={`critic recommends ${critic.recommendation}, advisory only`}
      >
        Critic: {critic.recommendation} (advisory)
      </Badge>
      <Caption1>{critic.advisory_notes}</Caption1>
    </div>
  );
}

function CriteriaBadges({ entry, stagger }: { entry: TranscriptEntry; stagger: boolean }) {
  const styles = useStyles();
  const reveal = useRevealStyles();
  return (
    <div className={styles.row}>
      {Object.entries(entry.verdict.criteria).map(([k, v], i) => (
        <Badge
          key={k}
          appearance="tint"
          role="img"
          aria-label={`${k}: ${v ? "pass" : "fail"}`}
          color={v ? "success" : "danger"}
          className={
            stagger
              ? mergeClasses(reveal.fadeIn, reveal[CRITERIA_DELAYS[i % CRITERIA_DELAYS.length]])
              : undefined
          }
        >
          {k}
        </Badge>
      ))}
    </div>
  );
}

function AttemptCard({
  entry,
  mode,
  visible,
}: {
  entry: TranscriptEntry;
  mode: "full" | "progressive";
  visible: VisibleState["arena"];
}) {
  const styles = useStyles();
  const reveal = useRevealStyles();
  const rejected = !entry.verdict.passed;
  const full = mode === "full";
  return (
    <Card
      appearance="subtle"
      className={mergeClasses(reveal.fadeIn, full && rejected && reveal.struck)}
    >
      <div className={styles.row}>
        <Badge appearance="outline">attempt {entry.attempt + 1}</Badge>
        {full && (
          <Badge
            appearance="filled"
            role="img"
            aria-label={entry.verdict.passed ? "passed" : "rejected"}
            color={entry.verdict.passed ? "success" : "danger"}
          >
            {entry.verdict.passed ? "PASS" : "REJECT"}
          </Badge>
        )}
        <Body1>
          citations:{" "}
          {entry.item.cited_ref_ids.length ? entry.item.cited_ref_ids.join(", ") : "(none)"}
        </Body1>
      </div>
      {(full || visible.stemVisible) && (
        <Body1
          block
          className={mergeClasses(
            styles.stem,
            !full && reveal.fadeIn,
            full && rejected && reveal.struckStem,
          )}
        >
          {entry.item.stem}
        </Body1>
      )}
      {entry.critic && (full || visible.criticVisible) && <CriticRow critic={entry.critic} />}
      {(full || visible.criteriaRevealed > 0) && (
        <CriteriaBadges entry={entry} stagger={!full} />
      )}
      {full &&
        rejected &&
        entry.verdict.failed_reasons.map((fr, i) => (
          <MessageBar key={i} intent="error">
            <MessageBarBody>
              <MessageBarTitle>{fr.criterion}</MessageBarTitle>
              {fr.reason}
            </MessageBarBody>
          </MessageBar>
        ))}
    </Card>
  );
}

export function AssessmentArena({ fixture, visible }: AssessmentArenaProps) {
  const styles = useStyles();
  const reveal = useRevealStyles();
  const { loop, targeted_skill } = fixture;
  const finished =
    visible.revealedAttempts >= loop.transcript.length && visible.currentAttempt === null;
  return (
    <Card>
      <Subtitle1>Adversarial Assessment Arena</Subtitle1>
      <Body1 block className={styles.intro}>
        Testing <Text as="strong" weight="semibold">{targeted_skill}</Text> — driven by edge{" "}
        <Text font="monospace">{loop.driving_edge_id}</Text>.
        {finished && (
          <>
            {" "}Loop status:{" "}
            <Badge
              appearance="filled"
              role="img"
              aria-label={`loop status: ${loop.status}`}
              color={loop.status === "verified" ? "success" : "danger"}
            >
              {loop.status}
            </Badge>
          </>
        )}
      </Body1>

      {loop.transcript.map((t, idx) => {
        if (idx < visible.revealedAttempts) {
          return <AttemptCard key={t.attempt} entry={t} mode="full" visible={visible} />;
        }
        if (idx === visible.currentAttempt) {
          return <AttemptCard key={t.attempt} entry={t} mode="progressive" visible={visible} />;
        }
        return null;
      })}

      {visible.showAbstain && (
        <MessageBar intent="warning" className={reveal.fadeIn}>
          <MessageBarBody>
            <MessageBarTitle>Fail-closed ABSTAIN</MessageBarTitle>
            The Evidence Gate could not verify a grounded item within {loop.attempts} attempts —
            no credential is minted. Refusing to certify is the feature, not the failure.
          </MessageBarBody>
        </MessageBar>
      )}
    </Card>
  );
}
