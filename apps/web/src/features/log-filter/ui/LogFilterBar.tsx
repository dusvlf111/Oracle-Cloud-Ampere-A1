"use client";

import * as React from "react";

import { levelBadgeClass } from "@/entities/log";
import { Button, Input, Label, cn } from "@/shared";

import {
  EMPTY_FILTER,
  LOG_LEVELS,
  type LogFilter,
  type LogLevel,
} from "../model/filter";

export interface LogFilterBarProps {
  value?: LogFilter;
  /** Fired with the full next filter whenever any control changes. */
  onChange: (filter: LogFilter) => void;
}

export function LogFilterBar({ value, onChange }: LogFilterBarProps) {
  const [filter, setFilter] = React.useState<LogFilter>(value ?? EMPTY_FILTER);
  // Collapsed by default on mobile (bottom-sheet style); always expanded from md up.
  const [mobileOpen, setMobileOpen] = React.useState(false);

  const update = React.useCallback(
    (patch: Partial<LogFilter>) => {
      setFilter((prev) => {
        const next = { ...prev, ...patch };
        onChange(next);
        return next;
      });
    },
    [onChange],
  );

  const toggleLevel = (level: LogLevel) => {
    update({
      levels: filter.levels.includes(level)
        ? filter.levels.filter((l) => l !== level)
        : [...filter.levels, level],
    });
  };

  return (
    <div className="border-b border-gray-200">
      {/* Mobile toggle: opens the filter panel as a bottom-sheet-style drawer. */}
      <button
        type="button"
        data-testid="log-filter-toggle"
        aria-expanded={mobileOpen}
        onClick={() => setMobileOpen((v) => !v)}
        className="flex min-h-11 w-full items-center justify-between px-3 text-sm font-medium text-gray-700 md:hidden"
      >
        Filters
        <span aria-hidden>{mobileOpen ? "▴" : "▾"}</span>
      </button>

      <div
        data-testid="log-filter-fields"
        className={cn(
          "flex-wrap items-end gap-3 p-3 md:flex",
          mobileOpen ? "flex" : "hidden",
        )}
      >
      <div className="flex flex-col gap-1">
        <Label>Levels</Label>
        <div className="flex gap-1" role="group" aria-label="Levels">
          {LOG_LEVELS.map((level) => {
            const active = filter.levels.includes(level);
            return (
              <button
                key={level}
                type="button"
                aria-pressed={active}
                onClick={() => toggleLevel(level)}
                className={cn(
                  "rounded px-1.5 py-0.5 text-xs font-semibold uppercase",
                  active ? levelBadgeClass(level) : "bg-gray-50 text-gray-400",
                )}
              >
                {level}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <Label htmlFor="log-filter-logger">Logger</Label>
        <Input
          id="log-filter-logger"
          placeholder="app.workers"
          value={filter.logger}
          onChange={(e) => update({ logger: e.target.value })}
        />
      </div>

      <div className="flex flex-col gap-1">
        <Label htmlFor="log-filter-config">Config ID</Label>
        <Input
          id="log-filter-config"
          inputMode="numeric"
          value={filter.configId}
          onChange={(e) => update({ configId: e.target.value })}
        />
      </div>

      <div className="flex flex-col gap-1">
        <Label htmlFor="log-filter-since">Since</Label>
        <Input
          id="log-filter-since"
          type="datetime-local"
          value={filter.since}
          onChange={(e) => update({ since: e.target.value })}
        />
      </div>

      <div className="flex flex-col gap-1">
        <Label htmlFor="log-filter-until">Until</Label>
        <Input
          id="log-filter-until"
          type="datetime-local"
          value={filter.until}
          onChange={(e) => update({ until: e.target.value })}
        />
      </div>

      <div className="flex flex-col gap-1">
        <Label htmlFor="log-filter-q">Search</Label>
        <Input
          id="log-filter-q"
          placeholder="message…"
          value={filter.q}
          onChange={(e) => update({ q: e.target.value })}
        />
      </div>

      <Button
        type="button"
        onClick={() => {
          setFilter(EMPTY_FILTER);
          onChange(EMPTY_FILTER);
        }}
      >
        Reset
      </Button>
      </div>
    </div>
  );
}
