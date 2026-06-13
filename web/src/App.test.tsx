import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { App } from "./App";

describe("App shell", () => {
  it("renders the primary nav with all three routes", () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole("link", { name: "Home" })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Architecture Tour" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "How it works" })
    ).toBeInTheDocument();
  });

  it("renders the Home page at the index route", () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(
      screen.getByRole("heading", { name: /your next role/i })
    ).toBeInTheDocument();
  });
});
