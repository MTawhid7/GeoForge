import { beforeEach, describe, expect, it } from "vitest";
import { migrateSeen, migrateSettings, migrateStats, recordResult, store } from "./local";
import type { Stats } from "./local";

const empty = (): Stats => store.stats();

beforeEach(() => localStorage.clear());

describe("migration", () => {
  it("reads a v0 blob rather than resetting someone's streak", () => {
    // v0 had no `v`, called the map `solved`, and stored booleans.
    const stats = migrateStats({ solved: { "gf-1": true }, streak: 4, lastDay: "2026-01-02" });
    expect(stats.results["gf-1"]).toBe("solved");
    expect(stats.streak).toBe(4);
    expect(stats.bestStreak).toBe(4);
    expect(stats.lastDay).toBe("2026-01-02");
  });

  it("drops values it does not recognise instead of trusting them", () => {
    const stats = migrateStats({ results: { a: "cheated", b: "assisted" }, streak: "many" });
    expect(stats.results).toEqual({ b: "assisted" });
    expect(stats.streak).toBe(0);
  });

  it("falls back to defaults on an unreadable blob", () => {
    localStorage.setItem("geoforge.stats", "{not json");
    expect(empty().streak).toBe(0);
  });

  it("keeps only a known theme", () => {
    expect(migrateSettings({ theme: "dark" }).theme).toBe("dark");
    expect(migrateSettings({ theme: "neon" }).theme).toBe("system");
    expect(migrateSettings({}).showLabels).toBe(true);
  });

  it("keeps only sane practice cursors", () => {
    expect(migrateSeen({ ids: ["a", 3], next: { easy: 2, hard: -1, medium: "x" } })).toEqual({
      v: 1,
      ids: ["a"],
      next: { easy: 2 },
    });
  });
});

describe("recording a result", () => {
  const options = { daily: true, day: "2026-03-02", band: "easy" };

  it("counts the puzzle and its band once", () => {
    const once = recordResult(empty(), "gf-1", "solved", options);
    const twice = recordResult(once, "gf-1", "solved", options);
    expect(twice.byBand.easy).toBe(1);
  });

  it("never downgrades an outcome", () => {
    const revealed = recordResult(empty(), "gf-1", "revealed", options);
    const solved = recordResult(revealed, "gf-1", "solved", options);
    expect(solved.results["gf-1"]).toBe("solved");
    const back = recordResult(solved, "gf-1", "revealed", options);
    expect(back.results["gf-1"]).toBe("solved");
  });
});

describe("the streak", () => {
  const daily = (stats: Stats, day: string) =>
    recordResult(stats, `p-${day}`, "solved", { daily: true, day, band: "easy" });

  it("starts at one", () => {
    expect(daily(empty(), "2026-03-02").streak).toBe(1);
  });

  it("grows on consecutive days", () => {
    let stats = daily(empty(), "2026-03-02");
    stats = daily(stats, "2026-03-03");
    stats = daily(stats, "2026-03-04");
    expect(stats.streak).toBe(3);
    expect(stats.bestStreak).toBe(3);
  });

  it("crosses a month boundary", () => {
    let stats = daily(empty(), "2026-02-28");
    stats = daily(stats, "2026-03-01");
    expect(stats.streak).toBe(2);
  });

  it("resets to one after a gap, keeping the best", () => {
    let stats = daily(empty(), "2026-03-02");
    stats = daily(stats, "2026-03-03");
    stats = daily(stats, "2026-03-09");
    expect(stats.streak).toBe(1);
    expect(stats.bestStreak).toBe(2);
  });

  it("does not move twice on one day", () => {
    let stats = daily(empty(), "2026-03-02");
    stats = recordResult(stats, "other", "solved", {
      daily: true,
      day: "2026-03-02",
      band: "hard",
    });
    expect(stats.streak).toBe(1);
  });

  it("does not move on a practice puzzle", () => {
    // Practice is unlimited, so counting it would measure how many puzzles exist rather than
    // whether someone came back.
    const stats = recordResult(empty(), "gf-1", "solved", {
      daily: false,
      day: "2026-03-02",
      band: "easy",
    });
    expect(stats.streak).toBe(0);
    expect(stats.lastDay).toBeNull();
  });
});

describe("persistence", () => {
  it("round-trips through localStorage", () => {
    const stats = recordResult(empty(), "gf-1", "assisted", {
      daily: true,
      day: "2026-03-02",
      band: "hard",
    });
    store.saveStats(stats);
    expect(store.stats()).toEqual(stats);
  });

  it("clears everything on reset", () => {
    store.saveSettings({ v: 1, theme: "dark", showLabels: false });
    store.saveSeen({ v: 1, ids: ["gf-1"], next: { easy: 4 } });
    store.reset();
    expect(store.settings().theme).toBe("system");
    expect(store.seen().ids).toEqual([]);
  });
});
