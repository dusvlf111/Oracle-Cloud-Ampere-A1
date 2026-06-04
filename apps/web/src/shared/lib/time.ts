/**
 * Human-friendly relative time ("3분 전", "방금 전") for dashboard timestamps.
 *
 * Pure + dependency-free so it is trivially unit-testable. Falls back to the
 * raw input for unparseable strings and treats null/undefined as "—".
 */
export function formatRelativeTime(
  iso: string | null | undefined,
  now: number = Date.now(),
): string {
  if (iso == null) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;

  const diffSec = Math.round((now - then) / 1000);
  if (diffSec < 0) return "방금 전";
  if (diffSec < 10) return "방금 전";
  if (diffSec < 60) return `${diffSec}초 전`;

  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}분 전`;

  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}시간 전`;

  const diffDay = Math.floor(diffHour / 24);
  return `${diffDay}일 전`;
}
