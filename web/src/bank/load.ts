// Fetching the bank: manifest first, shards on demand (docs/06 §6.5).
//
// The only judgement the frontend makes about a puzzle is whether it can read it at all.
// docs/02 is explicit: an unknown *major* schema version means refuse to read. Everything
// else — figure, marks, solution text — is rendered as the bank states it.

import { SCHEMA_VERSION } from "../types/generated/puzzle";
import type { Manifest, Puzzle, Shard } from "../types/generated/puzzle";

export const BANK_BASE = `${import.meta.env.BASE_URL}bank/`;

export class BankError extends Error {
  constructor(
    message: string,
    readonly kind: "missing" | "unreadable",
  ) {
    super(message);
    this.name = "BankError";
  }
}

const major = (version: string): string => version.split(".", 1)[0] ?? "";

export function assertReadable(version: string, where: string): void {
  if (major(version) !== major(SCHEMA_VERSION)) {
    throw new BankError(
      `${where} is schema ${version}; this build reads major ${major(SCHEMA_VERSION)} only`,
      "unreadable",
    );
  }
}

async function getJson(url: string): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(url);
  } catch (cause) {
    throw new BankError(`${url} could not be fetched: ${String(cause)}`, "missing");
  }
  if (!response.ok) {
    throw new BankError(`${url} returned ${response.status}`, "missing");
  }
  return (await response.json()) as unknown;
}

export async function loadManifest(base = BANK_BASE): Promise<Manifest> {
  const raw = (await getJson(`${base}manifest.json`)) as Manifest;
  assertReadable(raw.schema_version, "manifest");
  return raw;
}

export async function loadShard(shard: Shard, base = BANK_BASE): Promise<Puzzle[]> {
  const raw = (await getJson(`${base}${shard.file}`)) as Puzzle[];
  for (const puzzle of raw) {
    assertReadable(puzzle.schema_version ?? SCHEMA_VERSION, puzzle.id);
  }
  return raw;
}

/**
 * A lazily-filled view of the bank: knows how many puzzles exist in each band from the
 * manifest alone, and fetches a shard only when a puzzle from it is asked for.
 */
export class Bank {
  private readonly loaded = new Map<string, Puzzle[]>();

  constructor(
    readonly manifest: Manifest,
    private readonly base = BANK_BASE,
  ) {}

  /** Bands that actually have puzzles, in the manifest's order. */
  bands(): string[] {
    const seen: string[] = [];
    for (const shard of this.manifest.shards) {
      if (!seen.includes(shard.band)) seen.push(shard.band);
    }
    return seen;
  }

  countIn(band: string): number {
    return this.manifest.shards
      .filter((s) => s.band === band)
      .reduce((total, s) => total + s.puzzles, 0);
  }

  /** The `index`-th puzzle of `band`, counting across that band's shards in manifest order. */
  async at(band: string, index: number): Promise<Puzzle | null> {
    let remaining = index;
    for (const shard of this.manifest.shards) {
      if (shard.band !== band) continue;
      if (remaining < shard.puzzles) {
        const puzzles = await this.shard(shard);
        return puzzles[remaining] ?? null;
      }
      remaining -= shard.puzzles;
    }
    return null;
  }

  /** Global position `index` over every band in manifest order — what the daily pick uses. */
  async atGlobal(index: number): Promise<Puzzle | null> {
    let remaining = index;
    for (const shard of this.manifest.shards) {
      if (remaining < shard.puzzles) {
        const puzzles = await this.shard(shard);
        return puzzles[remaining] ?? null;
      }
      remaining -= shard.puzzles;
    }
    return null;
  }

  private async shard(shard: Shard): Promise<Puzzle[]> {
    const cached = this.loaded.get(shard.file);
    if (cached) return cached;
    const puzzles = await loadShard(shard, this.base);
    this.loaded.set(shard.file, puzzles);
    return puzzles;
  }
}
