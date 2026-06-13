import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { TransportBar } from "./TransportBar";
import type { TransportControls } from "./TransportBar";

function makeTransport(
  overrides: Partial<TransportControls> = {}
): TransportControls {
  return {
    playing: false,
    atEnd: false,
    elapsedMs: 0,
    totalMs: 60_000,
    toggle: vi.fn(),
    stepBack: vi.fn(),
    stepForward: vi.fn(),
    restart: vi.fn(),
    skipToEnd: vi.fn(),
    seek: vi.fn(),
    ...overrides,
  };
}

describe("TransportBar", () => {
  it("exposes accessible controls that fire the transport", () => {
    const transport = makeTransport();
    render(<TransportBar transport={transport} chapterLabel="Meet the flow" />);

    fireEvent.click(screen.getByRole("button", { name: "Play" }));
    expect(transport.toggle).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Step forward" }));
    expect(transport.stepForward).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Step back" }));
    expect(transport.stepBack).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Restart" }));
    expect(transport.restart).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Skip to end" }));
    expect(transport.skipToEnd).toHaveBeenCalledTimes(1);
  });

  it("shows Pause while playing", () => {
    render(
      <TransportBar
        transport={makeTransport({ playing: true })}
        chapterLabel="Meet the flow"
      />
    );
    expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
  });

  it("seeks via the scrubber", () => {
    const transport = makeTransport();
    render(<TransportBar transport={transport} chapterLabel="Meet the flow" />);
    fireEvent.change(screen.getByRole("slider", { name: "Tour position" }), {
      target: { value: "5000" },
    });
    expect(transport.seek).toHaveBeenCalledWith(5000);
  });

  it("formats elapsed and total time", () => {
    render(
      <TransportBar
        transport={makeTransport({ elapsedMs: 65_000, totalMs: 154_000 })}
        chapterLabel="Meet the flow"
      />
    );
    expect(screen.getByText("1:05 / 2:34")).toBeInTheDocument();
  });
});
