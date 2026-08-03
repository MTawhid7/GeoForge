// localStorage, versioned (docs/06 §6.5: no accounts, no state library, no analytics).
//
// Everything read from storage passes through a migration and a shape check. A player who
// has had the app open across two releases must not get a blank screen because a field they
// have never heard of changed name, so an unreadable blob is replaced by defaults rather than
// thrown — this is progress data, not a puzzle, and the failure mode for losing it is mild.

export const STORE_VERSION = 1;

const KEYS = {
  stats: "geoforge.stats",
  settings: "geoforge.settings",
  seen: "geoforge.seen",
} as const;

export type Outcome = "solved" | "assisted" | "revealed";

export interface Stats {
  v: number;
  /** puzzle id → how it ended. Absent means never finished. */
  results: Record<string, Outcome>;
  /**
   * band → puzzles finished in it. Counted here rather than derived from `results`, because
   * a puzzle id does not carry its band and deriving it would mean fetching every shard on
   * the home screen — the opposite of the lazy loading docs/06 §6.5 asks for.
   */
  byBand: Record<string, number>;
  streak: number;
  bestStreak: number;
  /** `YYYY-MM-DD` of the last day the daily puzzle was finished. */
  lastDay: string | null;
}

export type Theme = "system" | "light" | "dark";

export interface Settings {
  v: number;
  theme: Theme;
  showLabels: boolean;
}

export interface Seen {
  v: number;
  ids: string[];
  /** band → the index practice resumes at, so "Practice · Hard" does not restart every visit. */
  next: Record<string, number>;
}

export const defaultStats: Stats = {
  v: STORE_VERSION,
  results: {},
  byBand: {},
  streak: 0,
  bestStreak: 0,
  lastDay: null,
};
export const defaultSettings: Settings = { v: STORE_VERSION, theme: "system", showLabels: true };
export const defaultSeen: Seen = { v: STORE_VERSION, ids: [], next: {} };

function read<T>(key: string, fallback: T, migrate: (raw: Record<string, unknown>) => T): T {
  let text: string | null;
  try {
    text = localStorage.getItem(key);
  } catch {
    return fallback; // private mode, or storage disabled
  }
  if (text === null) return fallback;
  try {
    const raw: unknown = JSON.parse(text);
    if (typeof raw !== "object" || raw === null) return fallback;
    return migrate(raw as Record<string, unknown>);
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Quota or private mode. Losing progress is acceptable; crashing the player is not.
  }
}

/**
 * Bring a stored blob up to the current version.
 *
 * v0 is anything written before versioning existed — it has no `v`. It is read on a
 * best-effort basis field by field rather than discarded, because the alternative is silently
 * resetting a streak someone earned.
 */
export function migrateStats(raw: Record<string, unknown>): Stats {
  const results: Record<string, Outcome> = {};
  const stored = raw.results ?? raw.solved; // v0 called it `solved`
  if (typeof stored === "object" && stored !== null) {
    for (const [id, value] of Object.entries(stored as Record<string, unknown>)) {
      if (value === "solved" || value === "assisted" || value === "revealed") results[id] = value;
      else if (value === true) results[id] = "solved"; // v0 stored a boolean
    }
  }
  const byBand: Record<string, number> = {};
  if (typeof raw.byBand === "object" && raw.byBand !== null) {
    for (const [band, count] of Object.entries(raw.byBand as Record<string, unknown>)) {
      if (typeof count === "number" && Number.isFinite(count)) byBand[band] = count;
    }
  }
  const streak = typeof raw.streak === "number" ? raw.streak : 0;
  const best = typeof raw.bestStreak === "number" ? raw.bestStreak : streak;
  return {
    v: STORE_VERSION,
    results,
    byBand,
    streak,
    bestStreak: Math.max(best, streak),
    lastDay: typeof raw.lastDay === "string" ? raw.lastDay : null,
  };
}

export function migrateSettings(raw: Record<string, unknown>): Settings {
  const theme = raw.theme;
  return {
    v: STORE_VERSION,
    theme: theme === "light" || theme === "dark" ? theme : "system",
    showLabels: raw.showLabels !== false,
  };
}

export function migrateSeen(raw: Record<string, unknown>): Seen {
  const ids = Array.isArray(raw.ids)
    ? raw.ids.filter((id): id is string => typeof id === "string")
    : [];
  const next: Record<string, number> = {};
  if (typeof raw.next === "object" && raw.next !== null) {
    for (const [band, index] of Object.entries(raw.next as Record<string, unknown>)) {
      if (typeof index === "number" && Number.isInteger(index) && index >= 0) next[band] = index;
    }
  }
  return { v: STORE_VERSION, ids, next };
}

export const store = {
  stats: (): Stats => read(KEYS.stats, defaultStats, migrateStats),
  saveStats: (stats: Stats): void => write(KEYS.stats, stats),
  settings: (): Settings => read(KEYS.settings, defaultSettings, migrateSettings),
  saveSettings: (settings: Settings): void => write(KEYS.settings, settings),
  seen: (): Seen => read(KEYS.seen, defaultSeen, migrateSeen),
  saveSeen: (seen: Seen): void => write(KEYS.seen, seen),
  reset: (): void => {
    for (const key of Object.values(KEYS)) {
      try {
        localStorage.removeItem(key);
      } catch {
        // as above
      }
    }
  },
};

/** Yesterday's `YYYY-MM-DD`, given today's. Pure so the streak rule is testable. */
function previousDay(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  const date = new Date(y ?? 0, (m ?? 1) - 1, d ?? 1);
  date.setDate(date.getDate() - 1);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/**
 * Record a finished puzzle.
 *
 * The streak moves only on the *daily* puzzle: practice is unlimited, so counting it would
 * make the streak a measure of how many puzzles exist rather than of coming back. A day
 * already counted is idempotent; a gap resets to 1 rather than 0, because the day being
 * recorded is itself a day played.
 */
export function recordResult(
  stats: Stats,
  puzzleId: string,
  outcome: Outcome,
  options: { daily: boolean; day: string; band: string },
): Stats {
  const results = { ...stats.results };
  // Never downgrade: solving a puzzle you once revealed is still solved.
  const rank: Record<Outcome, number> = { revealed: 0, assisted: 1, solved: 2 };
  const previous = results[puzzleId];
  if (previous === undefined || rank[outcome] > rank[previous]) results[puzzleId] = outcome;

  const byBand = { ...stats.byBand };
  if (previous === undefined) byBand[options.band] = (byBand[options.band] ?? 0) + 1;

  let { streak, bestStreak, lastDay } = stats;
  if (options.daily && lastDay !== options.day) {
    streak = lastDay === previousDay(options.day) ? streak + 1 : 1;
    lastDay = options.day;
    bestStreak = Math.max(bestStreak, streak);
  }
  return { v: STORE_VERSION, results, byBand, streak, bestStreak, lastDay };
}
