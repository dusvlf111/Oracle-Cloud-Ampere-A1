import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { filterToQuery, type LogFilter } from "../model/filter";

import { LogFilterBar } from "./LogFilterBar";

describe("LogFilterBar", () => {
  it("toggles a level and reports it via onChange", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<LogFilterBar onChange={onChange} />);

    await user.click(screen.getByRole("button", { name: "ERROR", pressed: false }));
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ levels: ["ERROR"] }),
    );

    // Toggling off removes it again.
    await user.click(screen.getByRole("button", { name: "ERROR", pressed: true }));
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ levels: [] }),
    );
  });

  it("supports multiple selected levels", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<LogFilterBar onChange={onChange} />);

    await user.click(screen.getByRole("button", { name: "ERROR" }));
    await user.click(screen.getByRole("button", { name: "WARNING" }));
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ levels: ["ERROR", "WARNING"] }),
    );
  });

  it("reports logger / config / search text changes", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<LogFilterBar onChange={onChange} />);

    await user.type(screen.getByLabelText("Logger"), "app.api");
    await user.type(screen.getByLabelText("Config ID"), "5");
    await user.type(screen.getByLabelText("Search"), "auth");

    const last = onChange.mock.calls.at(-1)![0] as LogFilter;
    expect(last.logger).toBe("app.api");
    expect(last.configId).toBe("5");
    expect(last.q).toBe("auth");
  });

  it("renders a mobile toggle that opens/closes the filter panel", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<LogFilterBar onChange={onChange} />);

    const toggle = screen.getByTestId("log-filter-toggle");
    const fields = screen.getByTestId("log-filter-fields");

    // Collapsed by default on mobile (hidden class, md:flex keeps it open on desktop).
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(fields.className).toContain("hidden");

    await user.click(toggle);
    expect(screen.getByTestId("log-filter-toggle")).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByTestId("log-filter-fields").className).toContain("flex");
  });

  it("resets every field on Reset", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<LogFilterBar onChange={onChange} />);

    await user.type(screen.getByLabelText("Search"), "x");
    await user.click(screen.getByRole("button", { name: "ERROR" }));
    await user.click(screen.getByRole("button", { name: "Reset" }));

    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ levels: [], q: "", logger: "" }),
    );
  });
});

describe("filterToQuery", () => {
  it("serialises levels as repeated params and trims text", () => {
    const qs = filterToQuery({
      levels: ["ERROR", "WARNING"],
      logger: " app.workers ",
      configId: "5",
      since: "",
      until: "",
      q: "  auth ",
    });
    const params = new URLSearchParams(qs);
    expect(params.getAll("levels")).toEqual(["ERROR", "WARNING"]);
    expect(params.get("logger")).toBe("app.workers");
    expect(params.get("config_id")).toBe("5");
    expect(params.get("q")).toBe("auth");
  });

  it("converts datetime-local values to ISO and omits empty fields", () => {
    const qs = filterToQuery({
      levels: [],
      logger: "",
      configId: "",
      since: "2026-06-03T10:00",
      until: "",
      q: "",
    });
    const params = new URLSearchParams(qs);
    expect(params.get("since")).toMatch(/^2026-06-03T/);
    expect(params.has("until")).toBe(false);
    expect(params.has("logger")).toBe(false);
  });
});
