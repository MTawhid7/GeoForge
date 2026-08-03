import { describe, expect, it } from "vitest";
import { highlightKey, keySet, parseHighlight, segmentPair } from "./ids";

describe("parseHighlight", () => {
  it("reads each kind at its declared arity", () => {
    expect(parseHighlight("point:A")).toEqual({ kind: "point", at: ["A"] });
    expect(parseHighlight("seg:A:B")).toEqual({ kind: "seg", at: ["A", "B"] });
    expect(parseHighlight("angle:B:A:C")).toEqual({ kind: "angle", at: ["B", "A", "C"] });
    expect(parseHighlight("circle:O:A")).toEqual({ kind: "circle", at: ["O", "A"] });
    expect(parseHighlight("arc:A:B:C")).toEqual({ kind: "arc", at: ["A", "B", "C"] });
    expect(parseHighlight("region:R1")).toEqual({ kind: "region", at: ["R1"] });
  });

  it("refuses an id outside the grammar", () => {
    // The exact typo docs/02's grammar exists to catch: it used to render as nothing at all.
    expect(parseHighlight("segment:A:B")).toBeNull();
    expect(parseHighlight("seg:A")).toBeNull();
    expect(parseHighlight("seg:A:B:C")).toBeNull();
    expect(parseHighlight("")).toBeNull();
  });
});

describe("highlightKey", () => {
  it("treats a segment as unordered", () => {
    expect(highlightKey("seg:A:B")).toBe(highlightKey("seg:B:A"));
  });

  it("treats the two rays of an angle as unordered", () => {
    expect(highlightKey("angle:B:A:C")).toBe(highlightKey("angle:C:A:B"));
  });

  it("keeps angles with different vertices apart", () => {
    // ∠BAC and ∠ABC share three labels and are different angles. Sorting all three would
    // fuse them — the same mistake the schema's mark-backing check made and had to fix.
    expect(highlightKey("angle:B:A:C")).not.toBe(highlightKey("angle:A:B:C"));
  });

  it("leaves a circle's centre in place", () => {
    expect(highlightKey("circle:O:A")).not.toBe(highlightKey("circle:A:O"));
  });

  it("returns null for an unparseable id rather than a bogus key", () => {
    expect(highlightKey("segment:A:B")).toBeNull();
  });
});

describe("keySet", () => {
  it("collapses equivalent ids and drops junk", () => {
    expect(keySet(["seg:A:B", "seg:B:A", "nope"])).toEqual(new Set(["seg:A:B"]));
  });
});

describe("segmentPair", () => {
  it("reads the bare `A:B` form used inside marks", () => {
    expect(segmentPair("A:B")).toEqual(["A", "B"]);
    expect(segmentPair("seg:A:B")).toBeNull();
    expect(segmentPair("A")).toBeNull();
  });
});
