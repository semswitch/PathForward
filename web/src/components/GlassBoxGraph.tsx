// Glass-Box Reasoning Graph (Fluent UI v9 + Griffel).
// Renders the multi-hop traversal as an inspectable edge list. During replay,
// base edges appear first, then the DERIVED edges (CertGap/Readiness) — the
// facts that are NOT in the raw data. The driving edge pulses at the
// causal-spine beat, in sync with the credential chip in the Trust Console.
import {
  Card,
  Badge,
  Subtitle1,
  Text,
  Table,
  TableHeader,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
  mergeClasses,
} from "@fluentui/react-components";
import type { Fixture, GlassBoxEdge } from "../lib/contracts";
import type { VisibleState } from "../lib/visibleState";
import { useStyles } from "./GlassBoxGraph.styles";
import { useRevealStyles } from "./reveal.styles";

function edgeBadge(e: GlassBoxEdge, drivingId: string) {
  if (e.id === drivingId) return <Badge appearance="filled" color="severe">driving</Badge>;
  if (e.derived) return <Badge appearance="tint" color="danger">derived</Badge>;
  return <Badge appearance="outline" color="subtle">base</Badge>;
}

export interface GlassBoxGraphProps {
  fixture: Fixture;
  visible: VisibleState["glassbox"];
}

export function GlassBoxGraph({ fixture, visible }: GlassBoxGraphProps) {
  const styles = useStyles();
  const reveal = useRevealStyles();
  const { glassbox, driving_edge_id } = fixture;
  const gapNames = glassbox.meta.cert_gap_skill_ids;
  const edges = glassbox.edges.filter((e) =>
    e.derived ? visible.showDerivedEdges : visible.showBaseEdges,
  );
  return (
    <Card>
      <Subtitle1>Glass-Box Reasoning Graph</Subtitle1>
      {visible.showBaseEdges && (
        <div className={mergeClasses(styles.meta, reveal.fadeIn)}>
          <Badge appearance="outline">{glassbox.nodes.length} nodes</Badge>
          <Badge appearance="outline">{glassbox.edges.length} edges</Badge>
          {visible.showDerivedEdges && (
            <>
              <Badge appearance="tint" color="success">
                readiness {Math.round(glassbox.meta.readiness * 100)}%
              </Badge>
              <Text className={reveal.fadeIn}>
                CertGap (derived, not in raw data): {gapNames.join(", ")}
              </Text>
            </>
          )}
        </div>
      )}
      {edges.length > 0 && (
        <Table aria-label="Reasoning graph edges" size="small">
          <TableHeader>
            <TableRow>
              <TableHeaderCell>Edge</TableHeaderCell>
              <TableHeaderCell>Kind</TableHeaderCell>
              <TableHeaderCell>Provenance / validity</TableHeaderCell>
              <TableHeaderCell>Source</TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {edges.map((e) => (
              <TableRow
                key={e.id}
                data-edge-id={e.id}
                className={mergeClasses(
                  reveal.fadeIn,
                  visible.spineHighlight && e.id === driving_edge_id && reveal.spineHighlight,
                )}
              >
                <TableCell><Text font="monospace">{e.id}</Text></TableCell>
                <TableCell>{edgeBadge(e, driving_edge_id)}</TableCell>
                <TableCell>
                  {e.derived ? `${e.derivation_rule} · valid ${e.effective_at}` : `valid ${e.effective_at}`}
                </TableCell>
                <TableCell>
                  <Badge
                    appearance="tint"
                    role="img"
                    aria-label={`source ${e.source_badge}`}
                    color={e.source_badge.includes("Fabric") ? "informative" : "warning"}
                  >
                    {e.source_badge}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}
