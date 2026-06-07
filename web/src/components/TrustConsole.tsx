// Trust Console (skeleton, Fluent UI v9 + Griffel).
// Surfaces the invisible 60% (the rubric's Reliability weight): hero metrics, the
// cold-start calibration label, and the credential's causal-spine assertion. The
// live eval/red-team/OTel panels plug in here once Azure is wired.
import {
  Card,
  Badge,
  Subtitle1,
  Text,
  Table,
  TableBody,
  TableRow,
  TableCell,
} from "@fluentui/react-components";
import type { Fixture } from "../lib/contracts";
import { useStyles } from "./TrustConsole.styles";

export function TrustConsole({ fixture }: { fixture: Fixture }) {
  const styles = useStyles();
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
      <div className={styles.spine}>
        <Badge
          appearance="filled"
          role="img"
          aria-label={`causal spine ${spineOk ? "intact" : "broken"}`}
          color={spineOk ? "success" : "danger"}
        >
          causal spine {spineOk ? "intact" : "BROKEN"}
        </Badge>
        <Text font="monospace">credential cites {citedEdge || "(none)"}</Text>
      </div>
      <Table aria-label="Trust metrics" size="small">
        <TableBody>
          {rows.map(([k, v]) => (
            <TableRow key={k}>
              <TableCell>{k}</TableCell>
              <TableCell><Text font="monospace">{v}</Text></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
