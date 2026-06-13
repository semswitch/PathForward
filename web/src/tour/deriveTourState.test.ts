import { describe, it, expect } from "vitest";
import { makeBaseline } from "./baseline";
import { buildTourScript } from "./script";
import { deriveTourState } from "./deriveTourState";
import type { TourNode } from "./graph";

const beats = buildTourScript(makeBaseline());

const nodeById = (nodes: TourNode[], id: string) => {
  const node = nodes.find((n) => n.id === id);
  if (!node) throw new Error(`node ${id} missing from frame`);
  return node;
};

describe("deriveTourState", () => {
  it("starts all-dormant with nothing focused", () => {
    const frame = deriveTourState(beats, 0);
    for (const node of frame.nodes) {
      expect(node.data.status).toBe("dormant");
      expect(node.data.focused).toBe(false);
    }
    for (const edge of frame.edges) {
      expect(edge.className).toContain("edge-dormant");
    }
  });

  it("marks the gate rejected at the reject beat", () => {
    const rejectIndex = beats.findIndex(
      (b) => b.statusChanges?.gate === "rejected"
    );
    const frame = deriveTourState(beats, rejectIndex);
    expect(nodeById(frame.nodes, "gate").data.status).toBe("rejected");
  });

  it("restores earlier state when scrubbing backward (pure re-fold)", () => {
    const rejectIndex = beats.findIndex(
      (b) => b.statusChanges?.gate === "rejected"
    );
    // Visit the end, then scrub back before the rejection.
    deriveTourState(beats, beats.length - 1);
    const before = deriveTourState(beats, rejectIndex - 1);
    expect(["dormant", "active"]).toContain(
      nodeById(before.nodes, "gate").data.status
    );
    expect(nodeById(before.nodes, "mint").data.status).toBe("dormant");
  });

  it("accumulates traversed edges but keeps active edges current-beat-only", () => {
    const promptIndex = beats.findIndex((b) =>
      b.activeEdgeIds.includes("e-user-orch")
    );
    const later = deriveTourState(beats, promptIndex + 2);
    const userEdge = later.edges.find((e) => e.id === "e-user-orch");
    expect(userEdge?.className).toContain("edge-traversed");

    const current = deriveTourState(beats, promptIndex);
    const activeEdge = current.edges.find((e) => e.id === "e-user-orch");
    expect(activeEdge?.className).toContain("edge-active");
  });

  it("preserves the telemetry edge modifier across states", () => {
    const telIndex = beats.findIndex((b) =>
      b.activeEdgeIds.includes("e-gate-tel")
    );
    const frame = deriveTourState(beats, telIndex);
    const telEdge = frame.edges.find((e) => e.id === "e-gate-tel");
    expect(telEdge?.className).toBe("edge-telemetry edge-active");
  });

  it("ends with the credential minted and the ABSTAIN path shown", () => {
    const frame = deriveTourState(beats, beats.length - 1);
    expect(nodeById(frame.nodes, "mint").data.status).toBe("minted");
    expect(nodeById(frame.nodes, "credential").data.status).toBe("minted");
    expect(nodeById(frame.nodes, "gate").data.status).toBe("verified");
    expect(nodeById(frame.nodes, "abstain").data.status).toBe("abstained");
  });

  it("clamps out-of-range indices", () => {
    expect(deriveTourState(beats, -5).beatId).toBe(beats[0].id);
    expect(deriveTourState(beats, beats.length + 10).beatId).toBe(
      beats[beats.length - 1].id
    );
  });
});
