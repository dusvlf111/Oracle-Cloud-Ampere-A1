import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { LogEntry } from "@/entities/log";

import { LogStream } from "./LogStream";

function rows(n: number): LogEntry[] {
  return Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    timestamp: "2026-06-03T10:30:11.000Z",
    level: "INFO",
    logger: "app.x",
    message: `line ${i + 1}`,
    config_id: null,
    attempt_id: null,
    credential_id: null,
    extra: null,
    exc_info: null,
  }));
}

describe("LogStream", () => {
  it("renders rows and a line count", () => {
    render(
      <LogStream rows={rows(3)} paused={false} connected onTogglePause={vi.fn()} />,
    );
    expect(screen.getByText("line 1")).toBeInTheDocument();
    expect(screen.getByText(/3 lines/)).toBeInTheDocument();
    expect(screen.getByTestId("stream-status")).toHaveTextContent("(live)");
  });

  it("toggles pause via the button", async () => {
    const onToggle = vi.fn();
    const user = userEvent.setup();
    render(
      <LogStream rows={rows(1)} paused={false} connected onTogglePause={onToggle} />,
    );
    await user.click(screen.getByRole("button", { name: "Pause" }));
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it("shows paused status and a Resume button when paused", () => {
    render(
      <LogStream rows={rows(1)} paused connected={false} onTogglePause={vi.fn()} />,
    );
    expect(screen.getByTestId("stream-status")).toHaveTextContent("(paused)");
    expect(screen.getByRole("button", { name: "Resume" })).toBeInTheDocument();
  });
});
