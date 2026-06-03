import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AttemptStatusBadge } from "./AttemptStatusBadge";

describe("AttemptStatusBadge", () => {
  it.each([
    ["success", "success", "green"],
    ["out_of_capacity", "out of capacity", "amber"],
    ["rate_limited", "rate limited", "orange"],
    ["auth_error", "auth error", "red"],
    ["other_error", "error", "gray"],
  ])("renders %s with label/colour", (status, label, colour) => {
    render(<AttemptStatusBadge status={status} />);
    const badge = screen.getByTestId("attempt-status-badge");
    expect(badge).toHaveTextContent(label);
    expect(badge.className).toContain(colour);
    expect(badge.getAttribute("data-status")).toBe(status);
  });

  it("falls back to the raw status for unknown values", () => {
    render(<AttemptStatusBadge status="weird" />);
    expect(screen.getByTestId("attempt-status-badge")).toHaveTextContent("weird");
  });
});
