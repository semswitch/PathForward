// Adversarial Assessment Arena (skeleton, Fluent UI v9 + Griffel).
// Renders the Generator->Verifier transcript: each attempt with its pass/reject
// verdict, cited evidence, and the cited reason on rejection. The hero shot
// animates this reject->regenerate; the data contract is already what the loop emits.
import {
  Card,
  Badge,
  Subtitle1,
  Body1,
  Text,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
} from "@fluentui/react-components";
import type { Fixture } from "../lib/contracts";
import { useStyles } from "./AssessmentArena.styles";

export function AssessmentArena({ fixture }: { fixture: Fixture }) {
  const styles = useStyles();
  const { loop, targeted_skill } = fixture;
  return (
    <Card>
      <Subtitle1>Adversarial Assessment Arena</Subtitle1>
      <Body1 block className={styles.intro}>
        Testing <Text as="strong" weight="semibold">{targeted_skill}</Text> — driven by edge{" "}
        <Text font="monospace">{loop.driving_edge_id}</Text>. Loop status:{" "}
        <Badge
          appearance="filled"
          role="img"
          aria-label={`loop status: ${loop.status}`}
          color={loop.status === "verified" ? "success" : "danger"}
        >
          {loop.status}
        </Badge>
      </Body1>

      {loop.transcript.map((t) => (
        <Card key={t.attempt} appearance="subtle">
          <div className={styles.row}>
            <Badge appearance="outline">attempt {t.attempt}</Badge>
            <Badge
              appearance="filled"
              role="img"
              aria-label={t.verdict.passed ? "passed" : "rejected"}
              color={t.verdict.passed ? "success" : "danger"}
            >
              {t.verdict.passed ? "PASS" : "REJECT"}
            </Badge>
            <Body1>
              citations: {t.item.cited_ref_ids.length ? t.item.cited_ref_ids.join(", ") : "(none)"}
            </Body1>
          </div>
          <Body1 block className={styles.stem}>{t.item.stem}</Body1>
          {!t.verdict.passed &&
            t.verdict.failed_reasons.map((fr, i) => (
              <MessageBar key={i} intent="error">
                <MessageBarBody>
                  <MessageBarTitle>{fr.criterion}</MessageBarTitle>
                  {fr.reason}
                </MessageBarBody>
              </MessageBar>
            ))}
          {t.verdict.passed && (
            <div className={styles.row}>
              {Object.entries(t.verdict.criteria).map(([k, v]) => (
                <Badge
                  key={k}
                  appearance="tint"
                  role="img"
                  aria-label={`${k}: ${v ? "pass" : "fail"}`}
                  color={v ? "success" : "danger"}
                >
                  {k}
                </Badge>
              ))}
            </div>
          )}
        </Card>
      ))}
    </Card>
  );
}
