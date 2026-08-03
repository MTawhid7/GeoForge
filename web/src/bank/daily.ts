// The daily pick: a pure function of the calendar day and the bank's size.
//
// Deterministic and explicit rather than random, for the same reason everything offline is
// seeded — two devices opening the app on the same day must get the same puzzle, and a
// support question about "today's puzzle" has to be answerable without a server.

/** Local calendar day as `YYYY-MM-DD`. Local, not UTC: "today" is the player's today. */
export function dayKey(now: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** FNV-1a, 32-bit. Small, stable across engines, and not `Math.random`. */
function hash(text: string): number {
  let value = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    value ^= text.charCodeAt(i);
    value = Math.imul(value, 0x01000193) >>> 0;
  }
  return value >>> 0;
}

/** Index into the whole bank for `day`, or null when the bank is empty. */
export function dailyIndex(day: string, total: number): number | null {
  if (total <= 0) return null;
  return hash(day) % total;
}
