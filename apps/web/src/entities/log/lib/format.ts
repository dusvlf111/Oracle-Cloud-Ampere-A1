/** Tailwind classes for a level badge (PRD §7.6). */
export function levelBadgeClass(level: string): string {
  switch (level.toUpperCase()) {
    case "DEBUG":
      return "bg-gray-100 text-gray-600";
    case "INFO":
      return "bg-blue-100 text-blue-700";
    case "WARNING":
      return "bg-amber-100 text-amber-800";
    case "ERROR":
      return "bg-red-100 text-red-700";
    case "CRITICAL":
      return "bg-red-600 text-white";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

/** Render an ISO UTC timestamp in the viewer's local timezone. */
export function formatLocalTimestamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export const LOG_LEVEL_ORDER: Record<string, number> = {
  DEBUG: 10,
  INFO: 20,
  WARNING: 30,
  ERROR: 40,
  CRITICAL: 50,
};
