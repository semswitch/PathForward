// Glass-Box Reasoning Graph (skeleton).
// Renders the multi-hop traversal as an inspectable edge list, highlighting the
// DERIVED edges (CertGap/Readiness) and the driving edge. A force/graph layout
// (e.g. reactflow/d3) replaces this list view for the hero demo animation.
import {
  Tile, Tag, StructuredListWrapper, StructuredListHead, StructuredListBody,
  StructuredListRow, StructuredListCell,
} from "@carbon/react";
import type { Fixture, GlassBoxEdge } from "../lib/contracts";

function edgeTag(e: GlassBoxEdge, drivingId: string) {
  if (e.id === drivingId) return <Tag type="magenta">driving</Tag>;
  if (e.derived) return <Tag type="red">derived</Tag>;
  return <Tag type="gray">base</Tag>;
}

export function GlassBoxGraph({ fixture }: { fixture: Fixture }) {
  const { glassbox, driving_edge_id } = fixture;
  const gapNames = glassbox.meta.cert_gap_skill_ids;
  return (
    <Tile className="pf-panel">
      <h3>Glass-Box Reasoning Graph</h3>
      <div className="pf-row-spaced pf-panel">
        <Tag type="high-contrast">{glassbox.nodes.length} nodes</Tag>
        <Tag type="high-contrast">{glassbox.edges.length} edges</Tag>
        <Tag type="green">readiness {Math.round(glassbox.meta.readiness * 100)}%</Tag>
        <span>CertGap (derived, not in raw data): {gapNames.join(", ")}</span>
      </div>
      <StructuredListWrapper aria-label="Reasoning graph edges" isCondensed>
        <StructuredListHead>
          <StructuredListRow head>
            <StructuredListCell head>Edge</StructuredListCell>
            <StructuredListCell head>Kind</StructuredListCell>
            <StructuredListCell head>Provenance / validity</StructuredListCell>
            <StructuredListCell head>Source</StructuredListCell>
          </StructuredListRow>
        </StructuredListHead>
        <StructuredListBody>
          {glassbox.edges.map((e) => (
            <StructuredListRow key={e.id}>
              <StructuredListCell><span className="pf-mono">{e.id}</span></StructuredListCell>
              <StructuredListCell>{edgeTag(e, driving_edge_id)}</StructuredListCell>
              <StructuredListCell>
                {e.derived ? `${e.derivation_rule} · valid ${e.effective_at}` : `valid ${e.effective_at}`}
              </StructuredListCell>
              <StructuredListCell>
                <Tag type={e.source_badge.includes("Fabric") ? "blue" : "warm-gray"}>
                  {e.source_badge}
                </Tag>
              </StructuredListCell>
            </StructuredListRow>
          ))}
        </StructuredListBody>
      </StructuredListWrapper>
    </Tile>
  );
}
