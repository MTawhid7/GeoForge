// Figure metrics, in viewBox units.
//
// The figure is 1000 units wide and must be usable at 360 px (docs/06 §6.2), so one unit is
// 0.36 px at the narrowest supported width. Every size below is quoted with that reading, and
// docs/06 §6.4's "marks meet minimum stroke/size at 360 px" is what fixes the floor: nothing
// strokes thinner than 5 units (1.8 px) and no text is smaller than 30 units (10.8 px).
//
// These are render metrics, not thresholds on the data — the Python side owns everything that
// decides what a figure *is* (`LAYOUT` in src/geoforge/config/), including the point positions
// and the label offsets this file only draws at.

export const PX_PER_UNIT_AT_360 = 360 / 1000;

export const METRICS = {
  segment: 5,
  segmentHighlight: 13,
  circle: 5,
  point: 9,
  pointHighlight: 15,
  label: 34,
  markStroke: 5.5,
  arcRadius: 66,
  arcRadiusStep: 30,
  arcLabelGap: 30,
  arcLabel: 31,
  rightAngle: 44,
  tickHalf: 15,
  tickGap: 13,
  chevron: 26,
  chevronGap: 20,
  /** Padding around the viewBox so a label at the edge is not clipped by the SVG bounds. */
  pad: 26,
} as const;

/** Ticks/chevrons per congruence or parallel class; a fourth class reuses the first. */
export const MARK_CLASSES = 3;
