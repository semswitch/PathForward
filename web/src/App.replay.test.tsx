// Replay-mode integration tests. Like App.test.tsx these render the real App,
// which statically imports the generated fixture.json (regenerate with
// `python scripts/export_web_fixture.py` if absent).
import { describe, it, expect } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { App } from "./App";

describe("App replay", () => {
  it("starts at beat 0 with derived edges and credential hidden", () => {
    render(<App />);
    expect(screen.queryByText(/derived, not in raw data/)).not.toBeInTheDocument();
    expect(screen.queryByText(/causal spine/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "play replay" })).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "provenance: offline rehearsal" }),
    ).toBeInTheDocument();
  });

  it("skip to end reveals credential, metrics, plan, and the intact causal spine", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "skip to end" }));
    expect(screen.getByRole("img", { name: "causal spine intact" })).toBeInTheDocument();
    expect(screen.getByText("grounded-citation rate")).toBeInTheDocument();
    expect(screen.getByText("Learning Plan & Program Insights")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Learning plan phases" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /loop status/ })).toBeInTheDocument();
  });

  it("shows the agent pipeline rail", () => {
    render(<App />);
    expect(screen.getByRole("group", { name: "agent pipeline" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Evidence Gate — deterministic code/ })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Generator — reasoning agent/ })).toBeInTheDocument();
  });
});
