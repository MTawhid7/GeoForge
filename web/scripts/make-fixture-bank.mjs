// Cut a small fixture bank out of a real one: `node scripts/make-fixture-bank.mjs`.
//
// The fixture is committed (unlike `banks/`, which is a build artifact) because the tests and
// the Playwright run must not change meaning when the generator's corpus moves. It is a
// *subset* of real output rather than a hand-written puzzle: a hand-written figure would drift
// from what the pipeline actually emits, and the renderer would then be tested against a shape
// no bank contains.
//
// Regenerate after a schema change, and commit the result.

import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PER_BAND = 3;

const web = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(web, process.argv[2] ?? "../banks/v2");
const target = resolve(web, "fixtures/bank");

const manifest = JSON.parse(await readFile(resolve(source, "manifest.json"), "utf8"));

await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });

const shards = [];
const byBand = {};
for (const shard of manifest.shards) {
  const all = JSON.parse(await readFile(resolve(source, shard.file), "utf8"));
  const kept = all.slice(0, PER_BAND);
  if (kept.length === 0) continue;
  const payload = JSON.stringify(kept, null, 2);
  await writeFile(resolve(target, shard.file), payload);
  shards.push({
    band: shard.band,
    file: shard.file,
    puzzles: kept.length,
    sha256: createHash("sha256").update(payload).digest("hex"),
  });
  byBand[shard.band] = (byBand[shard.band] ?? 0) + kept.length;
}

const out = {
  ...manifest,
  by_band: byBand,
  puzzles: shards.reduce((n, s) => n + s.puzzles, 0),
  shards,
};
await writeFile(resolve(target, "manifest.json"), JSON.stringify(out, null, 2) + "\n");

for (const file of await readdir(target)) console.log(`fixtures/bank/${file}`);
console.log(`${out.puzzles} puzzles across ${Object.keys(byBand).length} bands`);
