import { describe, it, expect } from "vitest";
import { makeBaseline } from "./baseline";
import {
  CHAPTER_ORDER,
  buildTourScript,
  totalDurationMs,
} from "./script";
import { TOUR_EDGE_IDS, TOUR_NODE_IDS } from "./graph";

const beats = buildTourScript(makeBaseline());

describe("buildTourScript", () => {
  it("assigns unique beat ids", () => {
    const ids = beats.map((b) => b.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("assigns startMs cumulatively and strictly monotonically", () => {
    expect(beats[0].startMs).toBe(0);
    for (let i = 1; i < beats.length; i += 1) {
      expect(beats[i].startMs).toBe(
        beats[i - 1].startMs + beats[i - 1].durationMs
      );
      expect(beats[i].startMs).toBeGreaterThan(beats[i - 1].startMs);
    }
    expect(totalDurationMs(beats)).toBe(
      beats[beats.length - 1].startMs + beats[beats.length - 1].durationMs
    );
  });

  it("references only nodes and edges that exist in the graph", () => {
    const nodeIds = new Set<string>(TOUR_NODE_IDS);
    const edgeIds = new Set<string>(TOUR_EDGE_IDS);
    for (const beat of beats) {
      for (const id of beat.focusNodeIds) expect(nodeIds).toContain(id);
      for (const id of beat.activeEdgeIds) expect(edgeIds).toContain(id);
      for (const id of Object.keys(beat.statusChanges ?? {})) {
        expect(nodeIds).toContain(id);
      }
      for (const id of beat.camera?.nodeIds ?? []) expect(nodeIds).toContain(id);
    }
  });

  it("keeps chapters contiguous and in declared order", () => {
    const seen: string[] = [];
    for (const beat of beats) {
      if (seen[seen.length - 1] !== beat.chapter) seen.push(beat.chapter);
    }
    expect(new Set(seen).size).toBe(seen.length); // contiguous: no chapter revisited
    expect(seen).toEqual(
      CHAPTER_ORDER.filter((chapter) => seen.includes(chapter))
    );
    expect(seen).toEqual([...CHAPTER_ORDER]); // every chapter present
  });

  it("rejects before it verifies, and includes the ABSTAIN path", () => {
    const rejectIndex = beats.findIndex(
      (b) => b.statusChanges?.gate === "rejected"
    );
    const verifyIndex = beats.findIndex(
      (b) => b.statusChanges?.gate === "verified"
    );
    const abstainIndex = beats.findIndex(
      (b) => b.statusChanges?.abstain === "abstained"
    );
    expect(rejectIndex).toBeGreaterThanOrEqual(0);
    expect(verifyIndex).toBeGreaterThan(rejectIndex);
    expect(abstainIndex).toBeGreaterThan(verifyIndex);
  });

  it("writes a non-empty caption for every beat", () => {
    for (const beat of beats) {
      expect(beat.caption.trim().length).toBeGreaterThan(0);
    }
  });

  it("narrates the baseline run's real values", () => {
    const captions = beats.map((b) => b.caption).join(" ");
    const baseline = makeBaseline();
    expect(captions).toContain(baseline.workerId);
    expect(captions).toContain(baseline.targetRoleId);
    expect(captions).toContain(baseline.citedEdgeId);
    expect(captions).toContain(`${baseline.cohortSize} workers`);
    for (const criterion of baseline.attempt1FailedCriteria) {
      expect(captions).toContain(criterion);
    }
  });
});
