import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { OciConfigPaste } from "./OciConfigPaste";

const BLOCK = [
  "[DEFAULT]",
  "user=ocid1.user.oc1..aaapasted",
  "fingerprint=2a:69:11:22:33:44:55:66:77:88:99:aa:bb:cc:dd:ee",
  "tenancy=ocid1.tenancy.oc1..aaapasted",
  "region=ap-tokyo-1",
  "key_file=/home/me/.oci/key.pem",
].join("\n");

describe("OciConfigPaste", () => {
  it("is collapsed by default and expands on click", async () => {
    const user = userEvent.setup();
    render(<OciConfigPaste onParsed={vi.fn()} />);
    expect(screen.queryByLabelText("OCI config (ini)")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /구성 파일 붙여넣기/ }));
    expect(screen.getByLabelText("OCI config (ini)")).toBeInTheDocument();
  });

  it("parses on the 자동 채우기 button and reports ignored key_file", async () => {
    const onParsed = vi.fn();
    const user = userEvent.setup();
    render(<OciConfigPaste onParsed={onParsed} />);

    await user.click(screen.getByRole("button", { name: /구성 파일 붙여넣기/ }));
    const textarea = screen.getByLabelText("OCI config (ini)");
    textarea.focus();
    await user.paste(BLOCK);
    await user.click(screen.getByRole("button", { name: "자동 채우기" }));

    expect(onParsed).toHaveBeenCalledWith({
      user_ocid: "ocid1.user.oc1..aaapasted",
      fingerprint: "2a:69:11:22:33:44:55:66:77:88:99:aa:bb:cc:dd:ee",
      tenancy_ocid: "ocid1.tenancy.oc1..aaapasted",
      region: "ap-tokyo-1",
    });
    expect(screen.getByText(/4개 항목을 채웠습니다/)).toBeInTheDocument();
    expect(screen.getByText(/key_file 은 무시했습니다/)).toBeInTheDocument();
  });

  it("parses immediately on paste", async () => {
    const onParsed = vi.fn();
    const user = userEvent.setup();
    render(<OciConfigPaste onParsed={onParsed} />);

    await user.click(screen.getByRole("button", { name: /구성 파일 붙여넣기/ }));
    const textarea = screen.getByLabelText("OCI config (ini)");
    textarea.focus();
    await user.paste("region=ap-seoul-1");

    expect(onParsed).toHaveBeenCalledWith({ region: "ap-seoul-1" });
  });

  it("warns when nothing is recognised", async () => {
    const onParsed = vi.fn();
    const user = userEvent.setup();
    render(<OciConfigPaste onParsed={onParsed} />);

    await user.click(screen.getByRole("button", { name: /구성 파일 붙여넣기/ }));
    const textarea = screen.getByLabelText("OCI config (ini)");
    textarea.focus();
    await user.paste("just some prose");

    expect(onParsed).not.toHaveBeenCalled();
    expect(screen.getByText(/인식된 항목이 없습니다/)).toBeInTheDocument();
  });
});
