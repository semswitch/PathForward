// Adversarial Assessment Arena (skeleton, Fluent UI v9).
// Renders the Generator->Verifier transcript: each attempt with its pass/reject
// verdict, cited evidence, and the cited reason on rejection. The hero shot
// animates this reject->regenerate; the data contract is already what the loop emits.
import {
  Card, Badge, Subtitle1, Body1,
  MessageBar, MessageBarBody, MessageBarTitle,
} from "@fluentui/react-components";
import type { Fixture } from "../lib/contracts";

export function AssessmentArena({ fixture }: { fixture: Fixture }) {
  const { loop, targeted_skill } = fixture;
  return (
    <Card className="pf-panel">
      <Subtitle1>Adversarial Assessment Arena</Subtitle1>
      <Body1 block className="pf-panel">
        Testing <strong>{targeted_skill}</strong> — driven by edge{" "}
        <span className="pf-mono">{loop.driving_edge_id}</span>. Loop status:{" "}
        <Badge appearance="filled" color={loop.status === "verified" ? "success" : "danger"}>
          {loop.status}
        </Badge>
      </Body1>

      {loop.transcript.map((t) => (
        <Card key={t.attempt} appearance="subtle" className="pf-panel">
          <div className="pf-row-spaced">
            <Badge appearance="outline">attempt {t.attempt}</Badge>
            <Badge appearance="filled" color={t.verdict.passed ? "success" : "danger"}>
              {t.verdict.passed ? "PASS" : "REJECT"}
            </Badge>
            <Body1>
              citations: {t.item.cited_ref_ids.length ? t.item.cited_ref_ids.join(", ") : "(none)"}
            </Body1>
          </div>
          <Body1 block className="pf-panel">{t.item.stem}</Body1>
          {!t.verdict.passed &&
            t.verdict.failed_reasons.map((fr, i) => (
              <MessageBar key={i} intent="error" className="pf-panel">
                <MessageBarBody>
                  <MessageBarTitle>{fr.criterion}</MessageBarTitle>
                  {fr.reason}
                </MessageBarBody>
              </MessageBar>
            ))}
          {t.verdict.passed && (
            <div className="pf-row-spaced">
              {Object.entries(t.verdict.criteria).map(([k, v]) => (
                <Badge key={k} appearance="tint" color={v ? "success" : "danger"}>{k}</Badge>
              ))}
            </div>
          )}
        </Card>
      ))}
    </Card>
  );
}
