import { describe, expect, it } from "vitest";
import { dailyIndex, dayKey } from "./daily";

describe("dayKey", () => {
  it("uses the local calendar day", () => {
    expect(dayKey(new Date(2026, 2, 5, 23, 59))).toBe("2026-03-05");
    expect(dayKey(new Date(2026, 0, 1, 0, 0))).toBe("2026-01-01");
  });
});

describe("dailyIndex", () => {
  it("is the same for the same day", () => {
    expect(dailyIndex("2026-03-05", 217)).toBe(dailyIndex("2026-03-05", 217));
  });

  it("stays inside the bank", () => {
    for (let day = 1; day <= 28; day++) {
      const index = dailyIndex(`2026-02-${String(day).padStart(2, "0")}`, 7);
      expect(index).toBeGreaterThanOrEqual(0);
      expect(index).toBeLessThan(7);
    }
  });

  it("moves between days", () => {
    // A constant would give everyone the same puzzle forever; this is the cheap check that
    // the hash is doing something.
    const week = ["05", "06", "07", "08", "09", "10", "11"].map((d) =>
      dailyIndex(`2026-03-${d}`, 217),
    );
    expect(new Set(week).size).toBeGreaterThan(4);
  });

  it("has nothing to pick from an empty bank", () => {
    expect(dailyIndex("2026-03-05", 0)).toBeNull();
  });
});
