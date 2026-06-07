// Glass-Box Reasoning Graph (skeleton, Fluent UI v9).
// Renders the multi-hop traversal as an inspectable edge list, highlighting the
// DERIVED edges (CertGap/Readiness) and the driving edge. A force/graph layout
// (e.g. reactflow/d3) replaces this list view for the hero demo animation.
import {
  Card, Badge, Subtitle1, Text,
  Table, TableHeader, TableRow, TableHeaderCell, TableBody, TableCell,
} from "@fluentui/react-components";
import type { Fixture, GlassBoxEdge } from "../lib/contracts";

function edgeBadge(e: GlassBoxEdge, drivingId: string) {
  if (e.id === drivingId) return <Badge appearance="filled" color="severe">driving</Badge>;
  if (e.derived) return <Badge appearance="tint" color="danger">derived</Badge>;
  return <Badge appearance="outline" color="subtle">base</Badge>;
}

export function GlassBoxGraph({ fixture }: { fixture: Fixture }) {
  const { glassbox, driving_edge_id } = fixture;
  const gapNames = glassbox.meta.cert_gap_skill_ids;
  return (
    <Card className="pf-panel">
      <Subtitle1>Glass-Box Reasoning Graph</Subtitle1>
      <div className="pf-row-spaced pf-panel">
        <Badge appearance="outline">{glassbox.nodes.length} nodes</Badge>
        <Badge appearance="outline">{glassbox.edges.length} edges</Badge>
        <Badge appearance="tint" color="success">
          readiness {Math.round(glassbox.meta.readiness * 100)}%
        </Badge>
        <Text>CertGap (derived, not in raw data): {gapNames.join(", ")}</Text>
      </div>
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
          {glassbox.edges.map((e) => (
            <TableRow key={e.id}>
              <TableCell><span className="pf-mono">{e.id}</span></TableCell>
              <TableCell>{edgeBadge(e, driving_edge_id)}</TableCell>
              <TableCell>
                {e.derived ? `${e.derivation_rule} · valid ${e.effective_at}` : `valid ${e.effective_at}`}
              </TableCell>
              <TableCell>
                <Badge appearance="tint" color={e.source_badge.includes("Fabric") ? "informative" : "warning"}>
                  {e.source_badge}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
