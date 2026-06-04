import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { server } from "../../../../tests/mocks/server";
import { errorEnvelope } from "../../../../tests/mocks/handlers";

import { RegisterForm } from "./RegisterForm";

const REGISTER = "http://localhost:3000/api/auth/register";

async function fillAndSubmit(label: RegExp) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("사용자명"), "alice");
  await user.type(screen.getByLabelText("비밀번호"), "password123");
  await user.type(screen.getByLabelText("비밀번호 확인"), "password123");
  await user.click(screen.getByRole("button", { name: label }));
}

describe("RegisterForm", () => {
  it("setup mode: active result triggers auto-login callback", async () => {
    server.use(
      http.post(REGISTER, () =>
        HttpResponse.json(
          { username: "root", role: "admin", status: "active" },
          { status: 201 },
        ),
      ),
    );
    const onAutoLogin = vi.fn();
    const onPending = vi.fn();
    render(
      <RegisterForm mode="setup" onAutoLogin={onAutoLogin} onPending={onPending} />,
    );
    expect(
      screen.getByRole("button", { name: /관리자 계정 생성/ }),
    ).toBeInTheDocument();

    await fillAndSubmit(/관리자 계정 생성/);

    await waitFor(() => expect(onAutoLogin).toHaveBeenCalledTimes(1));
    expect(onPending).not.toHaveBeenCalled();
  });

  it("signup mode: pending result triggers onPending callback", async () => {
    server.use(
      http.post(REGISTER, () =>
        HttpResponse.json(
          { username: "alice", role: "user", status: "pending" },
          { status: 201 },
        ),
      ),
    );
    const onAutoLogin = vi.fn();
    const onPending = vi.fn();
    render(
      <RegisterForm mode="signup" onAutoLogin={onAutoLogin} onPending={onPending} />,
    );
    expect(screen.getByRole("button", { name: /가입 신청/ })).toBeInTheDocument();

    await fillAndSubmit(/가입 신청/);

    await waitFor(() => expect(onPending).toHaveBeenCalledTimes(1));
    expect(onPending.mock.calls[0][0]).toMatchObject({ username: "alice" });
    expect(onAutoLogin).not.toHaveBeenCalled();
  });

  it("shows a friendly message on 409 username_taken", async () => {
    server.use(
      http.post(REGISTER, () =>
        HttpResponse.json(errorEnvelope("username_taken", "taken"), {
          status: 409,
        }),
      ),
    );
    render(<RegisterForm mode="signup" />);
    await fillAndSubmit(/가입 신청/);

    expect(
      await screen.findByText(/이미 사용 중인 사용자명입니다/),
    ).toBeInTheDocument();
  });

  it("validates password confirmation locally", async () => {
    const user = userEvent.setup();
    render(<RegisterForm mode="signup" />);
    await user.type(screen.getByLabelText("사용자명"), "alice");
    await user.type(screen.getByLabelText("비밀번호"), "password123");
    await user.type(screen.getByLabelText("비밀번호 확인"), "different");
    await user.click(screen.getByRole("button", { name: /가입 신청/ }));

    expect(
      await screen.findByText(/비밀번호가 일치하지 않습니다/),
    ).toBeInTheDocument();
  });
});
