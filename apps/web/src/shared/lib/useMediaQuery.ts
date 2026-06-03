"use client";

import * as React from "react";

/**
 * SSR-safe media-query hook.
 *
 * Returns `false` during SSR and the first client render (no `window`), then
 * syncs to the real `matchMedia` result after mount. This avoids hydration
 * mismatches: the server and the first client paint always agree on `false`,
 * and the effect upgrades the value once the DOM is available.
 *
 * @example
 *   const isDesktop = useMediaQuery("(min-width: 768px)"); // Tailwind `md`
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = React.useCallback(
    (onChange: () => void) => {
      if (typeof window === "undefined" || !window.matchMedia) {
        return () => {};
      }
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    },
    [query],
  );

  const getSnapshot = React.useCallback(() => {
    if (typeof window === "undefined" || !window.matchMedia) {
      return false;
    }
    return window.matchMedia(query).matches;
  }, [query]);

  // Server snapshot is always `false` so SSR and first client paint match.
  const getServerSnapshot = React.useCallback(() => false, []);

  return React.useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
