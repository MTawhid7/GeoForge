// The figure renderer. Draws exactly what the JSON says, and nothing it says it does not.
//
// Draw order is z-order: circles, segments, marks, points, labels. Marks sit above segments
// so a tick is never buried under a highlight, and labels sit above everything because a
// label that a segment crosses is a label nobody can read.
//
// Highlighting varies **three** channels — colour, stroke width, and a dashed overlay
// (docs/06 §6.4: never colour alone). The overlay is a second element rather than a class
// swap so the base geometry stays visible underneath it.

import { useMemo } from "react";
import { VIEWBOX } from "../types/generated/puzzle";
import type { AngleArc, Figure as FigureData } from "../types/generated/puzzle";
import { arc, chevrons, mid, point as fmtPoint, rightAngle, ticks } from "./geometry";
import type { Vec } from "./geometry";
import { angleId, highlightKey, parseHighlight, segmentId, segmentPair } from "./ids";
import { MARK_CLASSES, METRICS } from "./style";

export interface FigureProps {
  figure: FigureData;
  /** Highlight ids to emphasise, in the docs/02 grammar. */
  highlights?: readonly string[];
  showLabels?: boolean;
  /** Tap-to-highlight (docs/06 §6.2). Receives the element's canonical id. */
  onSelect?: (id: string) => void;
  title: string;
}

export function Figure({
  figure,
  highlights = [],
  showLabels = true,
  onSelect,
  title,
}: FigureProps) {
  const coords = useMemo(() => {
    const map = new Map<string, Vec>();
    for (const p of figure.points) map.set(p.id, { x: p.x, y: p.y });
    return map;
  }, [figure]);

  const active = useMemo(() => {
    const keys = new Set<string>();
    for (const id of highlights) {
      const key = highlightKey(id);
      if (key !== null) keys.add(key);
    }
    return keys;
  }, [highlights]);

  const on = (id: string) => active.has(highlightKey(id) ?? id);
  const at = (name: string): Vec | null => coords.get(name) ?? null;

  const pad = METRICS.pad;
  const viewBox = `${-pad} ${-pad} ${VIEWBOX.width + 2 * pad} ${VIEWBOX.height + 2 * pad}`;

  // Arcs sharing a vertex are pushed outwards so two given angles at one point stay separate.
  const arcRank = new Map<AngleArc, number>();
  const perVertex = new Map<string, number>();
  for (const a of figure.marks?.angle_arcs ?? []) {
    const vertex = a.at[1];
    const rank = perVertex.get(vertex) ?? 0;
    arcRank.set(a, rank);
    perVertex.set(vertex, rank + 1);
  }

  const select = (id: string) => (onSelect ? () => onSelect(id) : undefined);

  return (
    <svg
      className="figure"
      viewBox={viewBox}
      role="img"
      aria-label={title}
      preserveAspectRatio="xMidYMid meet"
    >
      <title>{title}</title>

      <g className="figure-circles">
        {(figure.circles ?? []).map((c) => (
          <circle
            key={c.id}
            className={`fig-circle${on(c.id) ? " is-on" : ""}`}
            cx={c.cx}
            cy={c.cy}
            r={c.r}
            data-id={c.id}
          />
        ))}
      </g>

      <g className="figure-segments">
        {(figure.segments ?? []).map(([a, b]) => {
          const pa = at(a);
          const pb = at(b);
          if (!pa || !pb) return null;
          const id = segmentId(a, b);
          const lit = on(id);
          return (
            <g key={id} className={`fig-seg${lit ? " is-on" : ""}`} data-id={id}>
              <line x1={pa.x} y1={pa.y} x2={pb.x} y2={pb.y} className="fig-seg-base" />
              {lit && (
                <line x1={pa.x} y1={pa.y} x2={pb.x} y2={pb.y} className="fig-seg-halo" />
              )}
              <line
                x1={pa.x}
                y1={pa.y}
                x2={pb.x}
                y2={pb.y}
                className="fig-hit"
                onClick={select(id)}
              />
            </g>
          );
        })}
      </g>

      <g className="figure-marks">
        <EqualSegmentMarks figure={figure} at={at} />
        <ParallelMarks figure={figure} at={at} />
        <RightAngleMarks figure={figure} at={at} on={on} />
        <AngleArcMarks figure={figure} at={at} on={on} rank={arcRank} onSelect={onSelect} />
      </g>

      <g className="figure-points">
        {figure.points.map((p) => (
          <circle
            key={p.id}
            className={`fig-point${on(`point:${p.id}`) ? " is-on" : ""}`}
            cx={p.x}
            cy={p.y}
            r={METRICS.point}
            data-id={`point:${p.id}`}
            onClick={select(`point:${p.id}`)}
          />
        ))}
      </g>

      {showLabels && (
        <g className="figure-labels" aria-hidden="true">
          {figure.points.map((p) => (
            <text
              key={p.id}
              className={`fig-label${on(`point:${p.id}`) ? " is-on" : ""}`}
              x={p.x + (p.label_dx ?? 0)}
              y={p.y + (p.label_dy ?? 0)}
              fontSize={METRICS.label}
              textAnchor="middle"
              dominantBaseline="central"
            >
              {p.id}
            </text>
          ))}
        </g>
      )}
    </svg>
  );
}

type Locate = (name: string) => Vec | null;

function EqualSegmentMarks({ figure, at }: { figure: FigureData; at: Locate }) {
  const groups = figure.marks?.equal_segments ?? [];
  return (
    <>
      {groups.flatMap((group, index) =>
        group.flatMap((pair) => {
          const ends = segmentPair(pair);
          if (!ends) return [];
          const a = at(ends[0]);
          const b = at(ends[1]);
          if (!a || !b) return [];
          const count = (index % MARK_CLASSES) + 1;
          return ticks(a, b, count, METRICS.tickHalf, METRICS.tickGap).map((d, i) => (
            <path key={`${index}-${pair}-${i}`} className="fig-tick" d={d} />
          ));
        }),
      )}
    </>
  );
}

function ParallelMarks({ figure, at }: { figure: FigureData; at: Locate }) {
  const groups = figure.marks?.parallel ?? [];
  return (
    <>
      {groups.flatMap((group, index) =>
        group.flatMap((pair) => {
          const ends = segmentPair(pair);
          if (!ends) return [];
          const a = at(ends[0]);
          const b = at(ends[1]);
          if (!a || !b) return [];
          const count = (index % MARK_CLASSES) + 1;
          return chevrons(a, b, count, METRICS.chevron, METRICS.chevronGap).map((d, i) => (
            <path key={`${index}-${pair}-${i}`} className="fig-chevron" d={d} />
          ));
        }),
      )}
    </>
  );
}

function RightAngleMarks({
  figure,
  at,
  on,
}: {
  figure: FigureData;
  at: Locate;
  on: (id: string) => boolean;
}) {
  return (
    <>
      {(figure.marks?.right_angles ?? []).flatMap((id) => {
        const parsed = parseHighlight(id);
        if (parsed?.kind !== "angle") return [];
        const [p, v, q] = parsed.at;
        const pv = at(v);
        const pp = at(p);
        const pq = at(q);
        if (!pv || !pp || !pq) return [];
        const d = rightAngle(pv, pp, pq, METRICS.rightAngle);
        return d === null
          ? []
          : [<path key={id} className={`fig-right${on(id) ? " is-on" : ""}`} d={d} />];
      })}
    </>
  );
}

function AngleArcMarks({
  figure,
  at,
  on,
  rank,
  onSelect,
}: {
  figure: FigureData;
  at: Locate;
  on: (id: string) => boolean;
  rank: Map<AngleArc, number>;
  onSelect: ((id: string) => void) | undefined;
}) {
  return (
    <>
      {(figure.marks?.angle_arcs ?? []).flatMap((a) => {
        const [p, v, q] = a.at;
        const pv = at(v);
        const pp = at(p);
        const pq = at(q);
        if (!pv || !pp || !pq) return [];
        const radius = METRICS.arcRadius + (rank.get(a) ?? 0) * METRICS.arcRadiusStep;
        const geometry = arc(pv, pp, pq, radius, METRICS.arcLabelGap);
        if (geometry === null) return [];
        const id = angleId(p, v, q);
        const goal = a.kind === "goal";
        const cls = `fig-arc${goal ? " is-goal" : ""}${on(id) ? " is-on" : ""}`;
        return [
          <g key={`${id}-${a.label}`} className={cls} data-id={id} data-kind={a.kind ?? "given"}>
            <path d={geometry.path} className="fig-arc-path" onClick={onSelect && (() => onSelect(id))} />
            <text
              x={geometry.label.x}
              y={geometry.label.y}
              className="fig-arc-label"
              fontSize={METRICS.arcLabel}
              textAnchor="middle"
              dominantBaseline="central"
            >
              {a.label}
            </text>
          </g>,
        ];
      })}
    </>
  );
}

/** Exported for tests: where a length label would sit. Unused until `length` lands (P3). */
export const lengthLabelAnchor = (a: Vec, b: Vec): string => fmtPoint(mid(a, b));
