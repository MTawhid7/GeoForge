import { afterEach, describe, expect, it, vi } from "vitest";
import { Bank, BankError, assertReadable, loadManifest, loadShard } from "./load";
import { BASE, fixtureManifest, serveFixtureBank } from "../test/fixtures";

afterEach(() => vi.unstubAllGlobals());

describe("version gating", () => {
  it("reads the same major", () => {
    expect(() => assertReadable("2.7", "manifest")).not.toThrow();
  });

  it("refuses a newer major (docs/02)", () => {
    // Not a nicety: a major bump means a field the renderer does not know how to draw, and
    // drawing a figure with a piece missing is worse than saying the bank is too new.
    expect(() => assertReadable("3.0", "manifest")).toThrow(BankError);
    try {
      assertReadable("3.0", "manifest");
    } catch (error) {
      expect((error as BankError).kind).toBe("unreadable");
    }
  });
});

describe("loading", () => {
  it("reads the fixture manifest", async () => {
    serveFixtureBank();
    const manifest = await loadManifest(BASE);
    expect(manifest.puzzles).toBe(fixtureManifest().puzzles);
    expect(manifest.shippable).toBe(false);
  });

  it("reports a missing bank as missing, not as a crash", async () => {
    vi.stubGlobal("fetch", () => Promise.resolve(new Response("", { status: 404 })));
    await expect(loadManifest(BASE)).rejects.toMatchObject({ kind: "missing" });
  });

  it("reports a network failure as missing", async () => {
    vi.stubGlobal("fetch", () => Promise.reject(new Error("offline")));
    await expect(loadManifest(BASE)).rejects.toMatchObject({ kind: "missing" });
  });

  it("refuses a shard whose puzzles are too new", async () => {
    vi.stubGlobal("fetch", () =>
      Promise.resolve(new Response(JSON.stringify([{ id: "x", schema_version: "9.0" }]))),
    );
    await expect(
      loadShard({ file: "easy-000.json", band: "easy", puzzles: 1, sha256: "" }, BASE),
    ).rejects.toMatchObject({ kind: "unreadable" });
  });
});

describe("Bank", () => {
  it("counts each band from the manifest without fetching a shard", async () => {
    const served = serveFixtureBank();
    const bank = new Bank(await loadManifest(BASE), BASE);
    const counts = bank.bands().map((band) => bank.countIn(band));
    expect(counts.every((n) => n > 0)).toBe(true);
    expect(served.requested).toEqual([`${BASE}manifest.json`]);
  });

  it("fetches a shard once, however many puzzles are read from it", async () => {
    const served = serveFixtureBank();
    const bank = new Bank(await loadManifest(BASE), BASE);
    const band = bank.bands()[0] ?? "";
    await bank.at(band, 0);
    await bank.at(band, 1);
    expect(served.requested.filter((url) => url.includes(band))).toHaveLength(1);
  });

  it("walks the whole bank by global index", async () => {
    serveFixtureBank();
    const bank = new Bank(await loadManifest(BASE), BASE);
    const ids = new Set<string>();
    for (let i = 0; i < bank.manifest.puzzles; i++) {
      const puzzle = await bank.atGlobal(i);
      expect(puzzle).not.toBeNull();
      ids.add(puzzle?.id ?? "");
    }
    expect(ids.size).toBe(bank.manifest.puzzles);
  });

  it("returns null past the end rather than wrapping", async () => {
    serveFixtureBank();
    const bank = new Bank(await loadManifest(BASE), BASE);
    expect(await bank.atGlobal(bank.manifest.puzzles)).toBeNull();
    expect(await bank.at("nonexistent", 0)).toBeNull();
  });
});
