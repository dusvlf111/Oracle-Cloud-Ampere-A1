import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { ChannelTestButton } from "./ChannelTestButton";

const TEST = "http://localhost:3000/api/channels/2/test";

describe("ChannelTestButton", () => {
  it("shows a success result on ok:true", async () => {
    server.use(http.post(TEST, () => HttpResponse.json({ ok: true })));
    const user = userEvent.setup();
    render(<ChannelTestButton channelId={2} />);

    await user.click(screen.getByRole("button", { name: /send test/i }));
    expect(await screen.findByTestId("channel-test-result")).toHaveTextContent(
      /test sent/i,
    );
  });

  it("shows the error message on ok:false", async () => {
    server.use(
      http.post(TEST, () =>
        HttpResponse.json({ ok: false, error: "Connect timeout" }),
      ),
    );
    const user = userEvent.setup();
    render(<ChannelTestButton channelId={2} />);

    await user.click(screen.getByRole("button", { name: /send test/i }));
    expect(await screen.findByTestId("channel-test-result")).toHaveTextContent(
      "Connect timeout",
    );
  });
});
