import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Channel } from "../model/types";

import { ChannelCard } from "./ChannelCard";

function make(over: Partial<Channel> = {}): Channel {
  return {
    id: 2,
    name: "supabin ntfy",
    type: "ntfy",
    enabled: true,
    config: {
      server_url: "https://ntfy.supabin.com",
      topic: "oci-arm-alerts",
      token: "***xxx",
      priority: 4,
      tags: ["rocket"],
    },
    created_at: "2026-06-03T10:24:00Z",
    updated_at: "2026-06-03T10:24:00Z",
    ...over,
  };
}

describe("ChannelCard", () => {
  it("renders name, type label and masked config rows", () => {
    render(<ChannelCard channel={make()} />);
    expect(screen.getByText("supabin ntfy")).toBeInTheDocument();
    expect(screen.getByText("ntfy")).toBeInTheDocument();
    expect(screen.getByText("https://ntfy.supabin.com")).toBeInTheDocument();
    expect(screen.getByText("***xxx")).toBeInTheDocument(); // masked token verbatim
    expect(screen.getByText("rocket")).toBeInTheDocument(); // array joined
  });

  it("shows a type-specific icon per channel type", () => {
    const { rerender } = render(<ChannelCard channel={make({ type: "ntfy" })} />);
    expect(screen.getByTestId("channel-icon-ntfy")).toBeInTheDocument();

    rerender(<ChannelCard channel={make({ type: "discord" })} />);
    expect(screen.getByTestId("channel-icon-discord")).toBeInTheDocument();

    rerender(<ChannelCard channel={make({ type: "telegram" })} />);
    expect(screen.getByTestId("channel-icon-telegram")).toBeInTheDocument();

    rerender(<ChannelCard channel={make({ type: "slack" })} />);
    expect(screen.getByTestId("channel-icon-slack")).toBeInTheDocument();
  });

  it("reflects enabled/disabled state in the badge", () => {
    const { rerender } = render(<ChannelCard channel={make({ enabled: true })} />);
    expect(screen.getByTestId("channel-enabled-badge")).toHaveTextContent("enabled");

    rerender(<ChannelCard channel={make({ enabled: false })} />);
    expect(screen.getByTestId("channel-enabled-badge")).toHaveTextContent("disabled");
  });
});
