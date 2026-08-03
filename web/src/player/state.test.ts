import { describe, expect, it } from "vitest";
import { initialState, isFinished, reduce } from "./state";
import type { PlayerAction, PlayerRules, PlayerState } from "./state";
import type { Goal } from "../types/generated/puzzle";

const goal: Goal = {
  fact: "aconst:a:b:b:c=1/9",
  question: "∠ABC",
  quantity: { kind: "angle", at: ["A", "B", "C"] },
  answer: { exact: "20", approx: 20, display: "20°" },
  input: { mode: "keypad", exactness: "integer", unit: "deg", tolerance: null },
};

const rules: PlayerRules = { goal, steps: 3 };

const play = (actions: PlayerAction[], from = initialState, over = rules): PlayerState =>
  actions.reduce((state, action) => reduce(state, action, over), from);

const type = (text: string): PlayerAction[] =>
  [...text].map((value) => ({ type: "digit", value }) as PlayerAction);

describe("entry", () => {
  it("appends digits and deletes them", () => {
    expect(play([...type("123"), { type: "backspace" }]).entry).toBe("12");
    expect(play([...type("123"), { type: "clear" }]).entry).toBe("");
  });

  it("refuses a decimal point on an integer goal", () => {
    expect(play(type("2.5")).entry).toBe("25");
  });

  it("allows one decimal point when the goal is decimal", () => {
    const decimal = { goal: { ...goal, input: { ...goal.input, exactness: "decimal" } }, steps: 3 };
    expect(play(type("2.5.1"), initialState, decimal).entry).toBe("2.51");
  });

  it("stops growing at the entry limit", () => {
    expect(play(type("1234567890123")).entry).toHaveLength(8);
  });
});

describe("submitting", () => {
  it("counts a wrong answer, clears the field and bumps the shake", () => {
    const state = play([...type("21"), { type: "submit" }]);
    expect(state.verdict).toBe("wrong");
    expect(state.attempts).toBe(1);
    expect(state.entry).toBe("");
    expect(state.shake).toBe(1);
    expect(isFinished(state)).toBe(false);
  });

  it("does not count pressing Check on an empty field", () => {
    const state = play([{ type: "submit" }]);
    expect(state.verdict).toBe("empty");
    expect(state.attempts).toBe(0);
    expect(state.shake).toBe(0);
  });

  it("solves on the right answer", () => {
    const state = play([...type("20"), { type: "submit" }]);
    expect(state.status).toBe("solved");
    expect(state.attempts).toBe(1);
  });

  it("ignores input once the puzzle is finished", () => {
    const solved = play([...type("20"), { type: "submit" }]);
    expect(play([...type("9"), { type: "clear" }], solved)).toEqual(solved);
  });
});

describe("hints", () => {
  it("reveals one step at a time and stops at the last", () => {
    const state = play([{ type: "hint" }, { type: "hint" }, { type: "hint" }, { type: "hint" }]);
    expect(state.hintsShown).toBe(3);
  });

  it("still counts as solved when only some hints were taken", () => {
    // docs/06 §6.2 says *all* hints taken ⇒ assisted. Two of three is a solve, read literally.
    const state = play([{ type: "hint" }, { type: "hint" }, ...type("20"), { type: "submit" }]);
    expect(state.status).toBe("solved");
    expect(state.hintsShown).toBe(2);
  });

  it("marks a solve assisted once every hint was taken", () => {
    const state = play([
      { type: "hint" },
      { type: "hint" },
      { type: "hint" },
      ...type("20"),
      { type: "submit" },
    ]);
    expect(state.status).toBe("assisted");
  });

  it("can still be asked for a hint after finishing", () => {
    // The complete screen replays the whole solution, so the hint counter must not lock.
    const solved = play([...type("20"), { type: "submit" }]);
    expect(reduce(solved, { type: "hint" }, rules).hintsShown).toBe(1);
  });
});

describe("giving up", () => {
  it("reveals everything and is not a solve", () => {
    const state = play([{ type: "reveal" }]);
    expect(state.status).toBe("revealed");
    expect(state.hintsShown).toBe(3);
    expect(isFinished(state)).toBe(true);
  });
});
