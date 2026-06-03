import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { LogEntry } from "../model/types";

import { LogRow } from "./LogRow";

function makeEntry(over: Partial<LogEntry> = {}): LogEntry {
  return {
    id: 1,
    timestamp: "2026-06-03T10:30:11.000Z",
    level: "INFO",
    logger: "app.workers.poller",
    message: "poll start",
    config_id: null,
    attempt_id: null,
    credential_id: null,
    extra: null,
    exc_info: null,
    ...over,
  };
}

describe("LogRow", () => {
  it("renders message, logger and level badge", () => {
    render(<LogRow entry={makeEntry({ level: "WARNING", message: "hi there" })} />);
    expect(screen.getByText("hi there")).toBeInTheDocument();
    expect(screen.getByText("app.workers.poller")).toBeInTheDocument();
    const badge = screen.getByTestId("log-level-badge");
    expect(badge).toHaveTextContent("WARNING");
    expect(badge.className).toContain("amber");
  });

  it("renders both a short (mobile) and full (desktop) timestamp", () => {
    render(<LogRow entry={makeEntry({ timestamp: "2026-06-03T10:30:11.000Z" })} />);
    // The short variant (time only) and the full local timestamp both exist;
    // responsive classes hide one at a time at runtime.
    const seconds = screen.getAllByText(/:\d{2}/);
    expect(seconds.length).toBeGreaterThanOrEqual(2);
  });

  it("lets the message take full width and wrap on narrow screens", () => {
    render(<LogRow entry={makeEntry({ message: "a very long log message" })} />);
    const msg = screen.getByText("a very long log message");
    expect(msg.className).toContain("break-words");
    expect(msg.className).toContain("w-full");
  });

  it("uses distinct badge colours per level", () => {
    const { rerender } = render(<LogRow entry={makeEntry({ level: "ERROR" })} />);
    expect(screen.getByTestId("log-level-badge").className).toContain("red");

    rerender(<LogRow entry={makeEntry({ level: "INFO" })} />);
    expect(screen.getByTestId("log-level-badge").className).toContain("blue");
  });

  it("shows context chips for config/attempt/credential ids", () => {
    render(
      <LogRow entry={makeEntry({ config_id: 5, attempt_id: 142, credential_id: 1 })} />,
    );
    expect(screen.getByText("config:5")).toBeInTheDocument();
    expect(screen.getByText("attempt:142")).toBeInTheDocument();
    expect(screen.getByText("credential:1")).toBeInTheDocument();
  });

  it("expands and collapses the traceback", async () => {
    const user = userEvent.setup();
    render(
      <LogRow
        entry={makeEntry({
          level: "ERROR",
          exc_info: "Traceback (most recent call last): boom",
        })}
      />,
    );

    expect(screen.queryByTestId("log-traceback")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /expand details/i }));
    expect(screen.getByTestId("log-traceback")).toHaveTextContent("Traceback");
    await user.click(screen.getByRole("button", { name: /collapse details/i }));
    expect(screen.queryByTestId("log-traceback")).not.toBeInTheDocument();
  });

  it("renders no expand toggle when there are no details", () => {
    render(<LogRow entry={makeEntry()} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
