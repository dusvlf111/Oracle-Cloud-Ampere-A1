import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it, vi } from "vitest";

import type { LogEntry } from "@/entities/log";
import type {
  UseLogStreamOptions,
  UseLogStreamResult,
} from "@/widgets/log-stream";

import { server } from "../../../../tests/mocks/server";

import { LogsPage } from "./LogsPage";

const LOGS = "http://localhost:3000/api/logs";

function makeEntry(over: Partial<LogEntry>): LogEntry {
  return {
    id: 1,
    timestamp: "2026-06-03T10:30:11.000Z",
    level: "INFO",
    logger: "app.x",
    message: "m",
    config_id: null,
    attempt_id: null,
    credential_id: null,
    extra: null,
    exc_info: null,
    ...over,
  };
}

/** A stub stream hook so the page test never touches a real EventSource. */
function makeFakeStream() {
  const lastQuery = { current: "" };
  function useFakeStream(options: UseLogStreamOptions = {}): UseLogStreamResult {
    const [rows, setRows] = React.useState<LogEntry[]>([]);
    lastQuery.current = options.query ?? "";
    return {
      rows,
      paused: false,
      connected: true,
      setPaused: vi.fn(),
      prepend: (history) => setRows((p) => [...[...history].reverse(), ...p]),
      clear: () => setRows([]),
    };
  }
  return { useFakeStream, lastQuery };
}

describe("LogsPage", () => {
  it("loads historical logs on mount and renders rows", async () => {
    server.use(
      http.get(LOGS, () =>
        HttpResponse.json({
          items: [
            makeEntry({ id: 2, message: "newer" }),
            makeEntry({ id: 1, message: "older" }),
          ],
          next_cursor: null,
          has_more: false,
        }),
      ),
    );
    const { useFakeStream } = makeFakeStream();
    render(<LogsPage useStream={useFakeStream} />);

    expect(await screen.findByText("newer")).toBeInTheDocument();
    expect(screen.getByText("older")).toBeInTheDocument();
  });

  it("re-queries with the selected level filter", async () => {
    const seen: string[] = [];
    server.use(
      http.get(LOGS, ({ request }) => {
        seen.push(new URL(request.url).search);
        return HttpResponse.json({ items: [], next_cursor: null, has_more: false });
      }),
    );
    const { useFakeStream, lastQuery } = makeFakeStream();
    const user = userEvent.setup();
    render(<LogsPage useStream={useFakeStream} />);

    await waitFor(() => expect(seen.length).toBeGreaterThanOrEqual(1));
    await user.click(screen.getByRole("button", { name: "ERROR" }));

    await waitFor(() => expect(lastQuery.current).toContain("levels=ERROR"));
    expect(seen.some((s) => s.includes("levels=ERROR"))).toBe(true);
  });

  it("runs the delete-confirm flow and reloads", async () => {
    let deleteCalled = false;
    server.use(
      http.get(LOGS, () =>
        HttpResponse.json({ items: [], next_cursor: null, has_more: false }),
      ),
      http.delete(LOGS, () => {
        deleteCalled = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { useFakeStream } = makeFakeStream();
    const user = userEvent.setup();
    render(<LogsPage useStream={useFakeStream} />);

    await user.click(screen.getByRole("button", { name: /delete logs/i }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(deleteCalled).toBe(true));
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
  });

  it("cancels the delete dialog without calling the API", async () => {
    server.use(
      http.get(LOGS, () =>
        HttpResponse.json({ items: [], next_cursor: null, has_more: false }),
      ),
      http.delete(LOGS, () => {
        throw new Error("DELETE should not be called");
      }),
    );
    const { useFakeStream } = makeFakeStream();
    const user = userEvent.setup();
    render(<LogsPage useStream={useFakeStream} />);

    await user.click(screen.getByRole("button", { name: /delete logs/i }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
