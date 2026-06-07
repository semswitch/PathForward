import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { App } from "./App";

describe("App", () => {
  it("renders the title and the three hero surfaces", () => {
    render(<App />);
    expect(
      screen.getByRole("heading", { name: "PathForward", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText("Glass-Box Reasoning Graph")).toBeInTheDocument();
    expect(screen.getByText("Adversarial Assessment Arena")).toBeInTheDocument();
    expect(screen.getByText("Trust Console")).toBeInTheDocument();
  });
});
