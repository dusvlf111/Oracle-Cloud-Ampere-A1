import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Credential } from "../model/types";

import { CredentialCard } from "./CredentialCard";

function make(over: Partial<Credential> = {}): Credential {
  return {
    id: 1,
    name: "main",
    tenancy_ocid: "ocid1.tenancy.oc1..aaa***",
    user_ocid: "ocid1.user.oc1..aaa***",
    fingerprint: "ab:cd:**:**",
    region: "ap-chuncheon-1",
    has_passphrase: true,
    created_at: "2026-06-03T10:23:45Z",
    ...over,
  };
}

describe("CredentialCard", () => {
  it("renders name, region and server-masked identifiers", () => {
    render(<CredentialCard credential={make()} />);
    expect(screen.getByText("main")).toBeInTheDocument();
    expect(screen.getByText("ap-chuncheon-1")).toBeInTheDocument();
    expect(screen.getByText("ocid1.tenancy.oc1..aaa***")).toBeInTheDocument();
    expect(screen.getByText("ab:cd:**:**")).toBeInTheDocument();
  });

  it("shows the passphrase badge based on has_passphrase", () => {
    const { rerender } = render(<CredentialCard credential={make({ has_passphrase: true })} />);
    expect(screen.getByText("passphrase")).toBeInTheDocument();

    rerender(<CredentialCard credential={make({ has_passphrase: false })} />);
    expect(screen.getByText("no passphrase")).toBeInTheDocument();
  });

  it("renders the actions slot", () => {
    render(<CredentialCard credential={make()} actions={<button>verify</button>} />);
    expect(screen.getByRole("button", { name: "verify" })).toBeInTheDocument();
  });
});
