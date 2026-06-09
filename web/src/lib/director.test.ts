import { describe, it, expect } from "vitest";
import { buildBeats } from "./director";
import { makeAbstainFixture, makeFixture } from "./testFixture";

describe("buildBeats", () => {
  const fixture = makeFixture();
  const beats = buildBeats(fixture);

  it("assigns unique ids and positive durations", () => {
    const ids = beats.map((b) => b.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const b of beats) expect(b.durationMs).toBeGreaterThan(0);
  });

  it("orders each attempt: generator before gate verdict, one verdict per entry", () => {
    for (let i = 0; i < fixture.loop.transcript.length; i++) {
      const gen = beats.findIndex((b) => b.kind === "generator-proposes" && b.attempt === i);
      const verdicts = beats.filter((b) => b.kind === "gate-verdict" && b.attempt === i);
      expect(gen).toBeGreaterThanOrEqual(0);
      expect(verdicts).toHaveLength(1);
      expect(beats.indexOf(verdicts[0])).toBeGreaterThan(gen);
    }
    expect(beats.filter((b) => b.kind === "gate-verdict")).toHaveLength(
      fixture.loop.transcript.length,
    );
  });

  it("includes a critic beat only for entries with a critic review", () => {
    const criticBeats = beats.filter((b) => b.kind === "critic-reviews");
    expect(criticBeats).toHaveLength(
      fixture.loop.transcript.filter((t) => t.critic !== null).length,
    );
    const noCritic = makeFixture();
    noCritic.loop.transcript = noCritic.loop.transcript.map((t) => ({ ...t, critic: null }));
    expect(buildBeats(noCritic).filter((b) => b.kind === "critic-reviews")).toHaveLength(0);
  });

  it("mints only on the verified path, after the last verdict", () => {
    const mint = beats.findIndex((b) => b.kind === "mint");
    const lastVerdict = beats.map((b) => b.kind).lastIndexOf("gate-verdict");
    expect(mint).toBeGreaterThan(lastVerdict);
    expect(beats.some((b) => b.kind === "causal-spine")).toBe(true);
    expect(beats.some((b) => b.kind === "abstain")).toBe(false);
  });

  it("abstain path has abstain beat and no mint/causal-spine/planner/insights", () => {
    const abstainBeats = buildBeats(makeAbstainFixture());
    const kinds = abstainBeats.map((b) => b.kind);
    expect(kinds).toContain("abstain");
    expect(kinds).not.toContain("mint");
    expect(kinds).not.toContain("causal-spine");
    expect(kinds).not.toContain("planner");
    expect(kinds).not.toContain("insights");
    expect(kinds[kinds.length - 1]).toBe("closing");
  });

  it("skips the insights beat when insights are absent", () => {
    const noInsights = makeFixture({ insights: null });
    expect(buildBeats(noInsights).some((b) => b.kind === "insights")).toBe(false);
  });

  it("starts with the intro/derivation/curator chapters in order and ends with closing", () => {
    expect(beats.slice(0, 5).map((b) => b.kind)).toEqual([
      "worker-intro",
      "glassbox-base-edges",
      "glassbox-derived-edges",
      "curator-ranking",
      "curator-choice",
    ]);
    expect(beats[beats.length - 1].kind).toBe("closing");
  });
});
