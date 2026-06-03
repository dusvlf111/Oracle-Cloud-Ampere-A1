import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { LogEntry } from "@/entities/log";

import { useLogStream, type EventSourceCtor } from "./useLogStream";

/** Minimal EventSource mock that records instances and dispatches `log` events. */
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  closed = false;
  private listeners = new Map<string, Set<EventListener>>();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  addEventListener(type: string, fn: EventListener) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(fn);
  }
  removeEventListener(type: string, fn: EventListener) {
    this.listeners.get(type)?.delete(fn);
  }
  close() {
    this.closed = true;
  }
  emitLog(entry: Partial<LogEntry>) {
    const ev = new MessageEvent("log", { data: JSON.stringify(entry) });
    this.listeners.get("log")?.forEach((fn) => fn(ev));
  }
  static reset() {
    MockEventSource.instances = [];
  }
  static get last() {
    return MockEventSource.instances.at(-1)!;
  }
}

const Ctor = MockEventSource as unknown as EventSourceCtor;

describe("useLogStream", () => {
  it("appends rows from incoming log events", () => {
    MockEventSource.reset();
    const { result } = renderHook(() =>
      useLogStream({ eventSourceCtor: Ctor }),
    );

    expect(result.current.connected).toBe(true);
    act(() => MockEventSource.last.emitLog({ id: 1, message: "first" }));
    act(() => MockEventSource.last.emitLog({ id: 2, message: "second" }));

    expect(result.current.rows.map((r) => r.message)).toEqual([
      "first",
      "second",
    ]);
  });

  it("closes the EventSource (unsubscribes) when paused", () => {
    MockEventSource.reset();
    const { result } = renderHook(() =>
      useLogStream({ eventSourceCtor: Ctor }),
    );
    const opened = MockEventSource.last;

    act(() => result.current.setPaused(true));

    expect(opened.closed).toBe(true);
    expect(result.current.connected).toBe(false);
  });

  it("trims to maxRows, dropping the oldest", () => {
    MockEventSource.reset();
    const { result } = renderHook(() =>
      useLogStream({ eventSourceCtor: Ctor, maxRows: 3 }),
    );
    act(() => {
      for (let i = 1; i <= 5; i++) MockEventSource.last.emitLog({ id: i });
    });
    expect(result.current.rows.map((r) => r.id)).toEqual([3, 4, 5]);
  });

  it("encodes the active query into the stream URL", () => {
    MockEventSource.reset();
    renderHook(() =>
      useLogStream({ eventSourceCtor: Ctor, query: "levels=ERROR" }),
    );
    expect(MockEventSource.last.url).toBe("/api/logs/stream?levels=ERROR");
  });

  it("prepends reversed history ahead of live rows", () => {
    MockEventSource.reset();
    const { result } = renderHook(() =>
      useLogStream({ eventSourceCtor: Ctor }),
    );
    act(() => MockEventSource.last.emitLog({ id: 10, message: "live" }));
    act(() =>
      // newest-first history → rendered oldest-first before live rows
      result.current.prepend([
        { id: 3, message: "h3" } as LogEntry,
        { id: 2, message: "h2" } as LogEntry,
      ]),
    );
    expect(result.current.rows.map((r) => r.id)).toEqual([2, 3, 10]);
  });
});
