// Copy a bank into `public/bank/`, where the app fetches it from.
//
// The bank is a build artifact (`/banks/*` is gitignored), so it is copied in rather than
// imported: the frontend must load it the way a deployed app does — over HTTP, manifest first,
// shards lazily — and an import would compile the whole bank into the bundle and hide that.
//
//   node scripts/use-bank.mjs ../banks/v2      the real dev bank (`make bank`)
//   node scripts/use-bank.mjs fixtures/bank    the committed fixture bank (tests, e2e)

import { cp, mkdir, readFile, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const web = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(web, process.argv[2] ?? "../banks/v2");
const target = resolve(web, "public/bank");

if (!existsSync(resolve(source, "manifest.json"))) {
  console.error(
    `no bank at ${source} — build one with \`make bank\` from the repo root, ` +
      `or use \`npm run bank:fixture\` for the committed fixture bank`,
  );
  process.exit(1);
}

await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });
await cp(source, target, { recursive: true });

const manifest = JSON.parse(await readFile(resolve(target, "manifest.json"), "utf8"));
const shippable = manifest.shippable ? "shippable" : "NOT SHIPPABLE";
console.log(`bank: ${manifest.puzzles} puzzles from ${source} (${shippable})`);
if (!manifest.shippable) {
  console.log(`  still missing: ${manifest.missing_for_shippable.join(", ")}`);
}
