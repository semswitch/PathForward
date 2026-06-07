// Trust Console (skeleton).
// Surfaces the invisible 60% (the rubric's Reliability weight): hero metrics, the
// cold-start calibration label, and the credential's causal-spine assertion. The
// live eval/red-team/OTel panels plug in here once Azure is wired.
import {
  Tile, Tag, StructuredListWrapper, StructuredListBody, StructuredListRow,
  StructuredListCell,
} from "@carbon/react";
import type { Fixture } from "../lib/contracts";

export function TrustConsole({ fixture }: { fixture: Fixture }) {
  const { metrics, calibration, credential, driving_edge_id } = fixture;
  const subject = (credential.credentialSubject ?? {}) as Record<string, unknown>;
  const citedEdge = String(subject.cited_edge_id ?? "");
  const spineOk = citedEdge === driving_edge_id;

  const rows: [string, string][] = [
    ["grounded-citation rate", metrics.grounded_citation_rate],
    ["attempts to a verified item", `${metrics.attempts_to_verified} (${metrics.rejected_before_pass} rejected)`],
    ["readiness", `${metrics.readiness_pct}%`],
    ["ungrounded items minted into credentials", String(metrics.ungrounded_credentials)],
    ["calibration", `difficulty ${calibration.difficulty ?? "—"} · discrimination ${calibration.discrimination ?? "—"} · ${calibration.label ?? ""}`],
  ];

  return (
    <Tile className="pf-panel">
      <h3>Trust Console</h3>
      <div className="pf-row-spaced pf-panel">
        <Tag type={spineOk ? "green" : "red"}>
          causal spine {spineOk ? "intact" : "BROKEN"}
        </Tag>
        <span className="pf-mono">credential cites {citedEdge || "(none)"}</span>
      </div>
      <StructuredListWrapper aria-label="Trust metrics" isCondensed>
        <StructuredListBody>
          {rows.map(([k, v]) => (
            <StructuredListRow key={k}>
              <StructuredListCell>{k}</StructuredListCell>
              <StructuredListCell><span className="pf-mono">{v}</span></StructuredListCell>
            </StructuredListRow>
          ))}
        </StructuredListBody>
      </StructuredListWrapper>
    </Tile>
  );
}
