import { render, screen } from "@testing-library/react";
import * as React from "react";
import { describe, expect, it } from "vitest";

import type { Attempt } from "../model/types";

import { AttemptCardList } from "./AttemptCardList";

function attempt(over: Partial<Attempt> = {}): Attempt {
  return {
    id: 1,
    config_id: 5,
    attempted_at: "2026-06-03T10:30:11Z",
    status: "out_of_capacity",
    message: "Out of host capacity",
    instance_ocid: null,
    duration_ms: 1234,
    ...over,
  } as Attempt;
}

describe("AttemptCardList", () => {
  it("renders one card per attempt with status badge and duration", () => {
    render(
      <AttemptCardList
        attempts={[
          attempt({ id: 1, status: "success", instance_ocid: "ocid1.instance..ok", duration_ms: 2200 }),
          attempt({ id: 2, status: "out_of_capacity", duration_ms: 800 }),
        ]}
      />,
    );
    expect(screen.getAllByTestId("attempt-card")).toHaveLength(2);
    const badges = screen.getAllByTestId("attempt-status-badge");
    expect(badges[0]).toHaveTextContent("success");
    expect(badges[1]).toHaveTextContent("out of capacity");
    expect(screen.getByText("2.2 s")).toBeInTheDocument();
    expect(screen.getByText("800 ms")).toBeInTheDocument();
  });

  it("shows the instance OCID with break-all for narrow screens", () => {
    render(
      <AttemptCardList
        attempts={[attempt({ id: 3, status: "success", instance_ocid: "ocid1.instance..created" })]}
      />,
    );
    const ocid = screen.getByText("ocid1.instance..created");
    expect(ocid).toBeInTheDocument();
    expect(ocid.className).toContain("break-all");
  });

  it("falls back to the message when there is no OCID", () => {
    render(<AttemptCardList attempts={[attempt({ id: 4, message: "rate limited" })]} />);
    expect(screen.getByText("rate limited")).toBeInTheDocument();
  });

  it("renders nothing in the list for an empty array", () => {
    render(<AttemptCardList attempts={[]} />);
    expect(screen.queryByTestId("attempt-card")).not.toBeInTheDocument();
  });
});
