// Trust Console (Fluent UI v9 + Griffel).
// Surfaces the invisible 60% (the rubric's Reliability weight): the credential's
// causal-spine assertion and the hero trust metrics. During replay the
// credential section appears at the mint beat; the cited-edge chip pulses in
// sync with the driving edge row in the Glass-Box graph (the causal spine).
import {
  Card,
  Badge,
  Subtitle1,
  Text,
  Table,
  TableBody,
  TableRow,
  TableCell,
  mergeClasses,
} from "@fluentui/react-components";
import type { Fixture } from "../lib/contracts";
import type { VisibleState } from "../lib/visibleState";
import { useStyles } from "./TrustConsole.styles";
import { useRevealStyles } from "./reveal.styles";

export interface TrustConsoleProps {
  fixture: Fixture;
  visible: VisibleState["trust"];
}

export function TrustConsole({ fixture, visible }: TrustConsoleProps) {
  const styles = useStyles();
  const reveal = useRevealStyles();
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
    <Card>
      <Subtitle1>Trust Console</Subtitle1>
      {visible.showCredential && (
        <div className={mergeClasses(styles.spine, reveal.fadeIn)}>
          <Badge
            appearance="filled"
            role="img"
            aria-label={`causal spine ${spineOk ? "intact" : "broken"}`}
            color={spineOk ? "success" : "danger"}
          >
            causal spine {spineOk ? "intact" : "BROKEN"}
          </Badge>
          <Text
            font="monospace"
            data-edge-id={citedEdge}
            className={mergeClasses(visible.spineHighlight && reveal.spineHighlight)}
          >
            credential cites {citedEdge || "(none)"}
          </Text>
        </div>
      )}
      {visible.showMetrics && (
        <Table aria-label="Trust metrics" size="small" className={reveal.fadeIn}>
          <TableBody>
            {rows.map(([k, v]) => (
              <TableRow key={k}>
                <TableCell>{k}</TableCell>
                <TableCell><Text font="monospace">{v}</Text></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}
