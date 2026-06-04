import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RoleBadge } from "./RoleBadge";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it.each([
    ["pending", "Pending"],
    ["active", "Active"],
    ["disabled", "Disabled"],
  ])("renders the %s label", (status, label) => {
    render(<StatusBadge status={status} />);
    const badge = screen.getByTestId("user-status-badge");
    expect(badge).toHaveTextContent(label);
    expect(badge).toHaveAttribute("data-status", status);
  });

  it("falls back to the raw value for unknown status", () => {
    render(<StatusBadge status="weird" />);
    expect(screen.getByTestId("user-status-badge")).toHaveTextContent("weird");
  });
});

describe("RoleBadge", () => {
  it.each([
    ["admin", "Admin"],
    ["user", "User"],
  ])("renders the %s label", (role, label) => {
    render(<RoleBadge role={role} />);
    const badge = screen.getByTestId("user-role-badge");
    expect(badge).toHaveTextContent(label);
    expect(badge).toHaveAttribute("data-role", role);
  });
});
