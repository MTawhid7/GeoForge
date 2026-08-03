import { describe, expect, it } from "vitest";
import { arc, chevrons, rightAngle, ticks, unit } from "./geometry";

const P = (x: number, y: number) => ({ x, y });

describe("unit", () => {
  it("is null when the two points coincide, so nothing is drawn", () => {
    expect(unit({ x: 0, y: 0 })).toBeNull();
  });
});

describe("arc", () => {
  it("draws the sweep under a half-turn, whichever order the rays come in", () => {
    const forward = arc(P(0, 0), P(100, 0), P(0, 100), 40, 20);
    const backward = arc(P(0, 0), P(0, 100), P(100, 0), 40, 20);
    expect(forward?.path).toMatch(/^M /);
    // Opposite orders take opposite sweep flags but cover the same 90°, never the 270° one.
    expect(forward?.path).toContain(" 0 1 ");
    expect(backward?.path).toContain(" 0 0 ");
  });

  it("never asks for a large arc", () => {
    // A reflex sweep would draw an arc the puzzle does not mean. The large-arc flag is the
    // character before the sweep flag and must always be 0.
    for (const angle of [10, 90, 170, 200, 300, 359]) {
      const radians = (angle * Math.PI) / 180;
      const drawn = arc(
        P(0, 0),
        P(100, 0),
        P(100 * Math.cos(radians), 100 * Math.sin(radians)),
        40,
        20,
      );
      if (drawn) expect(drawn.path).toMatch(/A [\d.]+ [\d.]+ 0 0 [01] /);
    }
  });

  it("shrinks the radius rather than overshooting a short arm", () => {
    const drawn = arc(P(0, 0), P(10, 0), P(0, 400), 66, 20);
    const radius = Number(/A ([\d.]+) /.exec(drawn?.path ?? "")?.[1]);
    expect(radius).toBeLessThanOrEqual(10 * 0.32 + 1e-9);
  });

  it("returns null when an arm has no direction", () => {
    expect(arc(P(0, 0), P(0, 0), P(1, 0), 40, 20)).toBeNull();
    expect(arc(P(0, 0), P(1, 0), P(2, 0), 40, 20)).toBeNull();
  });

  it("puts the label outside the arc on the bisector", () => {
    // Arms of 100 clamp the radius to 32, so the label sits at 32 + 20 along the bisector.
    const drawn = arc(P(0, 0), P(100, 0), P(0, 100), 40, 20);
    expect(drawn?.label.x).toBeCloseTo(52 * Math.cos(Math.PI / 4), 5);
    expect(drawn?.label.y).toBeCloseTo(52 * Math.sin(Math.PI / 4), 5);
  });
});

describe("rightAngle", () => {
  it("draws three sides of a square", () => {
    const path = rightAngle(P(0, 0), P(100, 0), P(0, 100), 20);
    expect(path).toBe("M 20 0 L 20 20 L 0 20");
  });

  it("returns null on a degenerate arm", () => {
    expect(rightAngle(P(0, 0), P(0, 0), P(0, 100), 20)).toBeNull();
  });
});

describe("ticks", () => {
  it("draws one stroke per tick, centred on the segment", () => {
    const paths = ticks(P(0, 0), P(100, 0), 3, 10, 12);
    expect(paths).toHaveLength(3);
    expect(paths[1]).toBe("M 50 10 L 50 -10");
  });

  it("draws nothing for a zero-length segment", () => {
    expect(ticks(P(5, 5), P(5, 5), 2, 10, 12)).toEqual([]);
  });
});

describe("chevrons", () => {
  it("draws one chevron per class", () => {
    expect(chevrons(P(0, 0), P(100, 0), 2, 20, 16)).toHaveLength(2);
    expect(chevrons(P(0, 0), P(0, 0), 2, 20, 16)).toEqual([]);
  });
});
