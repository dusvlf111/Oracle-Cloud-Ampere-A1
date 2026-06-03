import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const SESSION_COOKIE = "session";
const LOGIN_PATH = "/login";

/**
 * Auth guard (PRD §7.7.4): redirect to /login when the session cookie is
 * absent. The /login route itself is excluded. Static assets and /api are
 * excluded via the `config.matcher` below.
 */
export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;

  if (pathname.startsWith(LOGIN_PATH)) {
    return NextResponse.next();
  }

  const hasSession = request.cookies.has(SESSION_COOKIE);
  if (!hasSession) {
    const url = request.nextUrl.clone();
    url.pathname = LOGIN_PATH;
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  // Exclude Next internals, static files and the proxied API from the guard.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api).*)"],
};
