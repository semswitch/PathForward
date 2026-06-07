// Adversarial Assessment Arena (skeleton).
// Renders the Generator->Verifier transcript: each attempt with its pass/reject
// verdict, cited evidence, and the cited reason on rejection. The hero shot
// animates this reject->regenerate; the data contract is already what the loop emits.
import { Tile, Tag, InlineNotification } from "@carbon/react";
import type { Fixture } from "../lib/contracts";

export function AssessmentArena({ fixture }: { fixture: Fixture }) {
  const { loop, targeted_skill } = fixture;
  return (
    <Tile className="pf-panel">
      <h3>Adversarial Assessment Arena</h3>
      <p className="pf-panel">
        Testing <strong>{targeted_skill}</strong> — driven by edge{" "}
        <span className="pf-mono">{loop.driving_edge_id}</span>. Loop status:{" "}
        <Tag type={loop.status === "verified" ? "green" : "red"}>{loop.status}</Tag>
      </p>

      {loop.transcript.map((t) => (
        <Tile key={t.attempt} className="pf-panel">
          <div className="pf-row-spaced">
            <Tag type="cool-gray">attempt {t.attempt}</Tag>
            <Tag type={t.verdict.passed ? "green" : "red"}>
              {t.verdict.passed ? "PASS" : "REJECT"}
            </Tag>
            <span>
              citations: {t.item.cited_ref_ids.length
                ? t.item.cited_ref_ids.join(", ")
                : "(none)"}
            </span>
          </div>
          <p className="pf-panel">{t.item.stem}</p>
          {!t.verdict.passed &&
            t.verdict.failed_reasons.map((fr, i) => (
              <InlineNotification
                key={i}
                kind="error"
                lowContrast
                hideCloseButton
                title={fr.criterion}
                subtitle={fr.reason}
              />
            ))}
          {t.verdict.passed && (
            <div className="pf-row-spaced">
              {Object.entries(t.verdict.criteria).map(([k, v]) => (
                <Tag key={k} type={v ? "green" : "red"}>{k}</Tag>
              ))}
            </div>
          )}
        </Tile>
      ))}
    </Tile>
  );
}
