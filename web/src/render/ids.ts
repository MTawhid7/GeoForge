// The normative highlight-id grammar (docs/02), read on the frontend side.
//
// `src/geoforge/schema.py` refuses to emit an id outside this grammar, so nothing here is a
// second gate — it is the parser that turns those ids into something a renderer can point at,
// plus the one thing the emitter cannot decide: *identity*. `seg:A:B` and `seg:B:A` name one
// segment and `angle:P:V:Q` and `angle:Q:V:P` name one angle, so highlighting has to compare
// canonical keys rather than strings.

export type Highlight =
  | { kind: "point"; at: [string] }
  | { kind: "seg"; at: [string, string] }
  | { kind: "angle"; at: [string, string, string] }
  | { kind: "circle"; at: [string, string] }
  | { kind: "arc"; at: [string, string, string] }
  | { kind: "region"; at: [string] };

const ARITY = { point: 1, seg: 2, angle: 3, circle: 2, arc: 3, region: 1 } as const;

export function parseHighlight(id: string): Highlight | null {
  const [kind, ...rest] = id.split(":");
  if (kind === undefined || !(kind in ARITY)) return null;
  const arity = ARITY[kind as keyof typeof ARITY];
  if (rest.length !== arity) return null;
  return { kind, at: rest } as Highlight;
}

/**
 * The identity of a highlighted element, so that equivalent ids compare equal.
 *
 * A segment is unordered. A vertex angle is the vertex plus its two rays as a set — which is
 * *not* the same as sorting all three labels: that would make ∠PVQ and ∠VPQ the same key, and
 * they are different angles. The same distinction the schema's mark-backing check turned on.
 */
export function highlightKey(id: string): string | null {
  const parsed = parseHighlight(id);
  if (parsed === null) return null;
  switch (parsed.kind) {
    case "seg":
      return `seg:${[...parsed.at].sort().join(":")}`;
    case "angle":
      return `angle:${parsed.at[1]}:${[parsed.at[0], parsed.at[2]].sort().join(":")}`;
    default:
      return id;
  }
}

export const segmentId = (a: string, b: string): string => `seg:${a}:${b}`;
export const angleId = (p: string, v: string, q: string): string => `angle:${p}:${v}:${q}`;

/** `Marks.equal_segments` and `Marks.parallel` hold bare `A:B` pairs, not `seg:` ids. */
export function segmentPair(pair: string): [string, string] | null {
  const parts = pair.split(":");
  return parts.length === 2 && parts[0] && parts[1] ? [parts[0], parts[1]] : null;
}

/** A set of canonical keys, for membership tests while rendering. */
export function keySet(ids: Iterable<string>): Set<string> {
  const keys = new Set<string>();
  for (const id of ids) {
    const key = highlightKey(id);
    if (key !== null) keys.add(key);
  }
  return keys;
}
