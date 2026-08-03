// The committed fixture bank, served to tests the way a static host would serve it.
//
// Real pipeline output (`scripts/make-fixture-bank.mjs` subsets a build), not a hand-written
// puzzle: a figure written by hand drifts from what the generator emits, and then the renderer
// is tested against a shape no bank contains.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { vi } from "vitest";
import type { Manifest, Puzzle } from "../types/generated/puzzle";

// From the vitest root (`web/`). Not `import.meta.url`: under the jsdom environment that is an
// http URL, and `fileURLToPath` rejects it.
const DIR = resolve(process.cwd(), "fixtures/bank") + "/";

export const BASE = "/bank/";

export const readFixture = (name: string): string => readFileSync(DIR + name, "utf8");

export const fixtureManifest = (): Manifest => JSON.parse(readFixture("manifest.json")) as Manifest;

export function fixturePuzzles(): Puzzle[] {
  return fixtureManifest().shards.flatMap(
    (shard) => JSON.parse(readFixture(shard.file)) as Puzzle[],
  );
}

/** The first puzzle of the fixture bank — the one the happy-path tests use. */
export const firstPuzzle = (): Puzzle => {
  const puzzle = fixturePuzzles()[0];
  if (!puzzle) throw new Error("the fixture bank is empty");
  return puzzle;
};

/**
 * Stub `fetch` with the fixture directory. Returns the list of requested paths so a test can
 * assert what was *not* fetched — lazy shard loading is a claim, not a hope (docs/06 §6.5).
 */
export function serveFixtureBank(): { requested: string[] } {
  const requested: string[] = [];
  vi.stubGlobal("fetch", (input: string | URL) => {
    const path = String(input);
    requested.push(path);
    const name = path.slice(path.lastIndexOf("/") + 1);
    try {
      const body = readFixture(name);
      return Promise.resolve(
        new Response(body, { status: 200, headers: { "content-type": "application/json" } }),
      );
    } catch {
      return Promise.resolve(new Response("", { status: 404 }));
    }
  });
  return { requested };
}
