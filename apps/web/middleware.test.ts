import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { middleware } from "./middleware";

function request(path: string, opts: { session?: string } = {}): NextRequest {
  const req = new NextRequest(new URL(`http://localhost:3000${path}`));
  if (opts.session) {
    req.cookies.set("session", opts.session);
  }
  return req;
}

describe("auth middleware", () => {
  it("redirects to /login when the session cookie is absent", () => {
    const res = middleware(request("/"));
    expect(res.status).toBe(307); // NextResponse.redirect
    expect(res.headers.get("location")).toBe("http://localhost:3000/login");
  });

  it("passes through when the session cookie is present", () => {
    const res = middleware(request("/", { session: "abc" }));
    // NextResponse.next() has no redirect location.
    expect(res.headers.get("location")).toBeNull();
  });

  it("never redirects the /login route itself", () => {
    const res = middleware(request("/login"));
    expect(res.headers.get("location")).toBeNull();
  });
});
