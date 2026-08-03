// Coordinates to SVG path data.
//
// **This is not geometry logic** in the sense CLAUDE.md forbids. Nothing here decides,
// derives, checks or reorders a geometric fact: every fact the figure shows was decided
// offline and arrives in the JSON. What these functions do is turn stated coordinates into
// stated pixels — an arc mark at `at: [P, V, Q]` cannot be drawn without knowing which way
// the two rays point, exactly as a segment cannot be drawn without reading two points.
// The line is: read coordinates, emit path data; never conclude anything from them.

export interface Vec {
  x: number;
  y: number;
}

export const sub = (a: Vec, b: Vec): Vec => ({ x: a.x - b.x, y: a.y - b.y });
export const add = (a: Vec, b: Vec): Vec => ({ x: a.x + b.x, y: a.y + b.y });
export const scale = (a: Vec, k: number): Vec => ({ x: a.x * k, y: a.y * k });
export const length = (a: Vec): number => Math.hypot(a.x, a.y);
export const mid = (a: Vec, b: Vec): Vec => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });

/** Unit vector, or null when the two points coincide — the caller then draws nothing. */
export function unit(v: Vec): Vec | null {
  const n = length(v);
  return n === 0 ? null : { x: v.x / n, y: v.y / n };
}

/** Rotated a quarter turn. In SVG's y-down frame this is the left normal on screen. */
export const perp = (v: Vec): Vec => ({ x: -v.y, y: v.x });

export const fmt = (n: number): string => (Math.round(n * 100) / 100).toString();
export const point = (v: Vec): string => `${fmt(v.x)} ${fmt(v.y)}`;

export interface ArcGeometry {
  path: string;
  /** Where a degree label goes: outside the arc, on the bisector. */
  label: Vec;
}

/**
 * The arc between rays VP and VQ, taking the sweep under a half-turn.
 *
 * Under a half-turn because that is the angle a human means by ∠PVQ, which is the angle the
 * puzzle's text names (docs/07 T1: the pipeline converts the engine's directed line angles to
 * human vertex angles before anything is published, so by the time it reaches here the
 * shorter sweep is the right one).
 */
export function arc(
  v: Vec,
  p: Vec,
  q: Vec,
  radius: number,
  labelGap: number,
): ArcGeometry | null {
  const toP = unit(sub(p, v));
  const toQ = unit(sub(q, v));
  if (toP === null || toQ === null) return null;

  const a1 = Math.atan2(toP.y, toP.x);
  const a2 = Math.atan2(toQ.y, toQ.x);
  let sweep = a2 - a1;
  while (sweep <= -Math.PI) sweep += 2 * Math.PI;
  while (sweep > Math.PI) sweep -= 2 * Math.PI;
  if (sweep === 0) return null;

  const r = Math.min(radius, 0.32 * length(sub(p, v)), 0.32 * length(sub(q, v)));
  const start = add(v, scale(toP, r));
  const end = add(v, scale(toQ, r));
  const flag = sweep > 0 ? 1 : 0;
  const bisector = a1 + sweep / 2;
  return {
    path: `M ${point(start)} A ${fmt(r)} ${fmt(r)} 0 0 ${flag} ${point(end)}`,
    label: add(v, { x: (r + labelGap) * Math.cos(bisector), y: (r + labelGap) * Math.sin(bisector) }),
  };
}

/** The little square drawn at a right angle, as an open three-sided path. */
export function rightAngle(v: Vec, p: Vec, q: Vec, size: number): string | null {
  const toP = unit(sub(p, v));
  const toQ = unit(sub(q, v));
  if (toP === null || toQ === null) return null;
  const s = Math.min(size, 0.4 * length(sub(p, v)), 0.4 * length(sub(q, v)));
  const a = add(v, scale(toP, s));
  const b = add(add(v, scale(toP, s)), scale(toQ, s));
  const c = add(v, scale(toQ, s));
  return `M ${point(a)} L ${point(b)} L ${point(c)}`;
}

/** `count` congruence ticks across the midpoint of AB. */
export function ticks(a: Vec, b: Vec, count: number, half: number, gap: number): string[] {
  const along = unit(sub(b, a));
  if (along === null) return [];
  const across = perp(along);
  const centre = mid(a, b);
  const first = -((count - 1) / 2) * gap;
  const out: string[] = [];
  for (let i = 0; i < count; i++) {
    const foot = add(centre, scale(along, first + i * gap));
    out.push(`M ${point(add(foot, scale(across, half)))} L ${point(add(foot, scale(across, -half)))}`);
  }
  return out;
}

/** `count` chevrons at the midpoint of AB, pointing along it — the parallel mark. */
export function chevrons(a: Vec, b: Vec, count: number, size: number, gap: number): string[] {
  const along = unit(sub(b, a));
  if (along === null) return [];
  const across = perp(along);
  const centre = mid(a, b);
  const first = -((count - 1) / 2) * gap;
  const out: string[] = [];
  for (let i = 0; i < count; i++) {
    const tip = add(centre, scale(along, first + i * gap + size / 2));
    const back = scale(along, -size);
    const wing = scale(across, size * 0.75);
    out.push(
      `M ${point(add(add(tip, back), wing))} L ${point(tip)} ` +
        `L ${point(add(add(tip, back), scale(wing, -1)))}`,
    );
  }
  return out;
}
