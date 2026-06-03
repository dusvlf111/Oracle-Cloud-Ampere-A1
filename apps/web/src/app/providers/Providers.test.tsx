import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Providers } from "./Providers";

describe("Providers", () => {
  it("renders children inside the QueryClientProvider", () => {
    render(
      <Providers>
        <span>hello</span>
      </Providers>,
    );
    expect(screen.getByText("hello")).toBeInTheDocument();
  });
});
