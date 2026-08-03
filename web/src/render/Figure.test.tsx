// The renderer, against every puzzle in the fixture bank rather than one contrived figure.
//
// The property that matters: **the figure draws what the JSON says and nothing else.** A mark
// with no backing given is the leak the schema's mark check and M5's anti-leak pass exist to
// stop; a segment the JSON does not list is the renderer inventing geometry.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Figure } from "./Figure";
import { highlightKey } from "./ids";
import { firstPuzzle, fixturePuzzles } from "../test/fixtures";
import type { Puzzle } from "../types/generated/puzzle";

const draw = (puzzle: Puzzle, highlights: string[] = [], showLabels = true) =>
  render(
    <Figure
      figure={puzzle.figure}
      highlights={highlights}
      showLabels={showLabels}
      title={puzzle.goal.question}
    />,
  ).container;

const puzzles = fixturePuzzles();

describe("what gets drawn", () => {
  it("draws exactly the segments the JSON lists", () => {
    for (const puzzle of puzzles) {
      const container = draw(puzzle);
      const drawn = [...container.querySelectorAll(".fig-seg")].map((g) =>
        g.getAttribute("data-id"),
      );
      const expected = (puzzle.figure.segments ?? []).map(([a, b]) => `seg:${a}:${b}`);
      expect(drawn).toEqual(expected);
    }
  });

  it("draws one dot per point", () => {
    for (const puzzle of puzzles) {
      expect(draw(puzzle).querySelectorAll(".fig-point")).toHaveLength(puzzle.figure.points.length);
    }
  });

  it("draws every angle arc, including the goal", () => {
    for (const puzzle of puzzles) {
      const arcs = draw(puzzle).querySelectorAll(".fig-arc");
      expect(arcs).toHaveLength(puzzle.figure.marks?.angle_arcs?.length ?? 0);
    }
  });

  it("marks the goal angle distinctly, exactly once", () => {
    for (const puzzle of puzzles) {
      const goals = draw(puzzle).querySelectorAll(".fig-arc.is-goal");
      expect(goals).toHaveLength(1);
      expect(goals[0]?.textContent).toBe("?");
    }
  });

  it("draws a square for every right angle and ticks for every congruence class", () => {
    for (const puzzle of puzzles) {
      const container = draw(puzzle);
      expect(container.querySelectorAll(".fig-right")).toHaveLength(
        puzzle.figure.marks?.right_angles?.length ?? 0,
      );
      const parallels = (puzzle.figure.marks?.parallel ?? []).reduce(
        (total, group, index) => total + group.length * ((index % 3) + 1),
        0,
      );
      expect(container.querySelectorAll(".fig-chevron")).toHaveLength(parallels);
    }
  });

  it("hides labels when asked, and shows one per point otherwise", () => {
    const puzzle = firstPuzzle();
    expect(draw(puzzle, [], true).querySelectorAll(".fig-label")).toHaveLength(
      puzzle.figure.points.length,
    );
    expect(draw(puzzle, [], false).querySelectorAll(".fig-label")).toHaveLength(0);
  });

  it("has an accessible name naming the goal", () => {
    render(
      <Figure figure={firstPuzzle().figure} showLabels title="Figure for the goal angle" />,
    );
    expect(screen.getByRole("img", { name: "Figure for the goal angle" })).toBeInTheDocument();
  });
});

describe("highlighting", () => {
  it("lights the elements a given names, and only those", () => {
    for (const puzzle of puzzles) {
      const given = puzzle.given.find((g) => (g.highlights ?? []).length > 0);
      if (!given) continue;
      const container = draw(puzzle, [...(given.highlights ?? [])]);
      const wanted = new Set(
        (given.highlights ?? []).map(highlightKey).filter((k): k is string => k !== null),
      );
      for (const element of container.querySelectorAll("[data-id]")) {
        const key = highlightKey(element.getAttribute("data-id") ?? "");
        if (key === null) continue;
        const lit = element.classList.contains("is-on");
        expect(lit).toBe(wanted.has(key));
      }
    }
  });

  it("accepts a highlight written with its points the other way round", () => {
    const puzzle = puzzles.find((p) => (p.figure.segments ?? []).length > 0);
    const segment = puzzle?.figure.segments?.[0];
    if (!puzzle || !segment) throw new Error("no fixture puzzle has a segment");
    const reversed = draw(puzzle, [`seg:${segment[1]}:${segment[0]}`]);
    expect(reversed.querySelectorAll(".fig-seg.is-on")).toHaveLength(1);
  });

  it("ignores a highlight outside the grammar instead of throwing", () => {
    expect(() => draw(firstPuzzle(), ["segment:A:B", "seg:A"])).not.toThrow();
    expect(draw(firstPuzzle(), ["segment:A:B"]).querySelectorAll(".is-on")).toHaveLength(0);
  });

  it("draws the dashed overlay only on a highlighted segment (colour is not the only channel)", () => {
    const puzzle = puzzles.find((p) => (p.figure.segments ?? []).length > 0);
    const segment = puzzle?.figure.segments?.[0];
    if (!puzzle || !segment) throw new Error("no fixture puzzle has a segment");
    expect(draw(puzzle).querySelectorAll(".fig-seg-halo")).toHaveLength(0);
    expect(
      draw(puzzle, [`seg:${segment[0]}:${segment[1]}`]).querySelectorAll(".fig-seg-halo"),
    ).toHaveLength(1);
  });
});

describe("robustness", () => {
  it("skips an element naming a point the figure does not have", () => {
    // Cannot happen from this pipeline — the schema checks it — but a renderer that throws
    // takes the whole screen down, and a renderer that skips loses one mark.
    const puzzle = firstPuzzle();
    const broken = {
      ...puzzle.figure,
      segments: [...(puzzle.figure.segments ?? []), ["A", "ZZ"] as [string, string]],
    };
    expect(() =>
      render(<Figure figure={broken} showLabels title="broken" />),
    ).not.toThrow();
  });

  it("draws every circle the JSON declares", () => {
    // Currently zero across the whole corpus: circles are declared by 7 of 56 realized figures
    // and none survives premise pruning. So this is a fixture test, and the count is reported
    // rather than hidden.
    const declared = puzzles.reduce((n, p) => n + (p.figure.circles?.length ?? 0), 0);
    expect(declared).toBe(0);

    const container = render(
      <Figure
        figure={{
          points: [{ id: "A", x: 100, y: 100 }],
          circles: [{ id: "circle:O:A", cx: 500, cy: 375, r: 200, center_point: "O" }],
        }}
        showLabels
        title="one circle"
      />,
    ).container;
    expect(container.querySelectorAll(".fig-circle")).toHaveLength(1);
  });
});
