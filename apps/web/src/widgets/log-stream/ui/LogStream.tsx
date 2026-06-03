"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import * as React from "react";

import { LogRow, type LogEntry } from "@/entities/log";
import { Button } from "@/shared";

export interface LogStreamProps {
  rows: LogEntry[];
  paused: boolean;
  connected: boolean;
  onTogglePause: () => void;
  /** Above this many rows the list virtualises (PRD §7.6). */
  virtualizeThreshold?: number;
}

const ROW_HEIGHT = 28;

export function LogStream({
  rows,
  paused,
  connected,
  onTogglePause,
  virtualizeThreshold = 500,
}: LogStreamProps) {
  const parentRef = React.useRef<HTMLDivElement>(null);
  const stickToBottom = React.useRef(true);

  const virtualize = rows.length > virtualizeThreshold;

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 12,
    enabled: virtualize,
  });

  // Auto-scroll to bottom on new rows while streaming and pinned to bottom.
  React.useEffect(() => {
    const el = parentRef.current;
    if (!el || paused || !stickToBottom.current) return;
    if (virtualize) {
      virtualizer.scrollToIndex(rows.length - 1, { align: "end" });
    } else {
      el.scrollTop = el.scrollHeight;
    }
  }, [rows.length, paused, virtualize, virtualizer]);

  // Scrolling up un-pins (and pauses); scrolling back to the bottom re-pins.
  const onScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const atBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight < ROW_HEIGHT * 1.5;
    if (!atBottom && stickToBottom.current) {
      stickToBottom.current = false;
      if (!paused) onTogglePause();
    } else if (atBottom) {
      stickToBottom.current = true;
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-gray-200 px-3 py-2">
        <span className="text-sm text-gray-500">
          {rows.length} lines{" "}
          <span
            data-testid="stream-status"
            className={connected ? "text-green-600" : "text-gray-400"}
          >
            {paused ? "(paused)" : connected ? "(live)" : "(idle)"}
          </span>
        </span>
        <Button type="button" onClick={onTogglePause}>
          {paused ? "Resume" : "Pause"}
        </Button>
      </div>

      <div
        ref={parentRef}
        data-testid="log-scroll"
        onScroll={onScroll}
        className="flex-1 overflow-auto"
      >
        {virtualize ? (
          <div
            style={{ height: virtualizer.getTotalSize(), position: "relative" }}
          >
            {virtualizer.getVirtualItems().map((vi) => (
              <div
                key={vi.key}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  transform: `translateY(${vi.start}px)`,
                }}
              >
                <LogRow entry={rows[vi.index]} />
              </div>
            ))}
          </div>
        ) : (
          rows.map((entry) => <LogRow key={entry.id} entry={entry} />)
        )}
      </div>
    </div>
  );
}
