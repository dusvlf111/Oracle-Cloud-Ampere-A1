import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Config } from "../model/types";

import { ConfigRow } from "./ConfigRow";

function make(over: Partial<Config> = {}): Config {
  return {
    id: 5,
    name: "ARM 4OCPU main",
    credential_id: 1,
    enabled: true,
    shape: "VM.Standard.A1.Flex",
    ocpus: 4,
    memory_gb: 24,
    boot_volume_gb: 50,
    image_ocid: "ocid1.image",
    subnet_ocid: "ocid1.subnet",
    availability_domain: "Uocm:AP-CHUNCHEON-1-AD-1",
    ssh_public_key: "ssh-ed25519 AAAA",
    retry_interval_sec: 60,
    max_attempts: null,
    channel_ids: [1, 2],
    created_at: "2026-06-03T10:24:00Z",
    updated_at: "2026-06-03T10:24:00Z",
    ...over,
  };
}

describe("ConfigRow", () => {
  it("renders name and shape/spec summary", () => {
    render(<ConfigRow config={make()} />);
    expect(screen.getByText("ARM 4OCPU main")).toBeInTheDocument();
    expect(screen.getByText(/4 OCPU/)).toBeInTheDocument();
    expect(screen.getByText(/24 GB/)).toBeInTheDocument();
  });

  it("toggles the enabled badge label/colour", () => {
    const { rerender } = render(<ConfigRow config={make({ enabled: true })} />);
    let badge = screen.getByTestId("config-enabled-badge");
    expect(badge).toHaveTextContent("enabled");
    expect(badge.className).toContain("green");

    rerender(<ConfigRow config={make({ enabled: false })} />);
    badge = screen.getByTestId("config-enabled-badge");
    expect(badge).toHaveTextContent("disabled");
    expect(badge.className).toContain("gray");
  });

  it("shows a channel count chip when channels are attached", () => {
    render(<ConfigRow config={make({ channel_ids: [1, 2, 3] })} />);
    expect(screen.getByText("3 channels")).toBeInTheDocument();
  });

  it("omits the channel chip when there are no channels", () => {
    render(<ConfigRow config={make({ channel_ids: [] })} />);
    expect(screen.queryByText(/channel/)).not.toBeInTheDocument();
  });
});
