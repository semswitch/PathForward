import { describe, it, expect } from "vitest";
import { buildBeats } from "./director";
import { deriveVisibleState } from "./visibleState";
import { makeAbstainFixture, makeFixture } from "./testFixture";

describe("deriveVisibleState", () => {
  const fixture = makeFixture();
  const beats = buildBeats(fixture);
  const at = (i: number) => deriveVisibleState(fixture, beats, i);
  const indexOf = (kind: string, attempt?: number) =>
    beats.findIndex((b) => b.kind === kind && (attempt === undefined || b.attempt === attempt));

  it("reveals everything at the last beat", () => {
    const v = at(beats.length - 1);
    expect(v.glassbox).toEqual({
      showBaseEdges: true,
      showDerivedEdges: true,
      spineHighlight: true,
    });
    expect(v.curator).toEqual({ showRanking: true, showChoice: true });
    expect(v.arena.revealedAttempts).toBe(fixture.loop.transcript.length);
    expect(v.arena.currentAttempt).toBeNull();
    expect(v.trust).toEqual({ showCredential: true, spineHighlight: true, showMetrics: true });
    expect(v.plan.visible).toBe(true);
    expect(v.insights.visible).toBe(true);
  });

  it("hides derived edges before their beat", () => {
    const v = at(indexOf("glassbox-base-edges"));
    expect(v.glassbox.showBaseEdges).toBe(true);
    expect(v.glassbox.showDerivedEdges).toBe(false);
  });

  it("keeps the rejected attempt revealed while the next attempt is in progress", () => {
    const v = at(indexOf("generator-proposes", 1));
    expect(v.arena.revealedAttempts).toBe(1); // attempt 0's verdict already seen
    expect(v.arena.currentAttempt).toBe(1);
    expect(v.arena.stemVisible).toBe(true);
    expect(v.arena.criticVisible).toBe(false); // critic beat for attempt 1 not yet played
    expect(v.arena.criteriaRevealed).toBe(0);
  });

  it("reveals criteria for the current attempt only after its gate-criteria beat", () => {
    const v = at(indexOf("gate-criteria", 0));
    expect(v.arena.currentAttempt).toBe(0);
    expect(v.arena.criteriaRevealed).toBe(5);
  });

  it("turns spine highlight on at the causal-spine beat and keeps it on after", () => {
    const spine = indexOf("causal-spine");
    expect(at(spine - 1).glassbox.spineHighlight).toBe(false);
    expect(at(spine).glassbox.spineHighlight).toBe(true);
    expect(at(beats.length - 1).glassbox.spineHighlight).toBe(true);
    expect(at(spine).trust.spineHighlight).toBe(true);
  });

  it("abstain path: showAbstain on, credential and plan never visible", () => {
    const abstainFixture = makeAbstainFixture();
    const abstainBeats = buildBeats(abstainFixture);
    const v = deriveVisibleState(abstainFixture, abstainBeats, abstainBeats.length - 1);
    expect(v.arena.showAbstain).toBe(true);
    expect(v.arena.revealedAttempts).toBe(3);
    expect(v.trust.showCredential).toBe(false);
    expect(v.trust.showMetrics).toBe(true);
    expect(v.plan.visible).toBe(false);
    expect(v.insights.visible).toBe(false);
  });
});
