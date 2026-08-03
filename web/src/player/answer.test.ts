import { describe, expect, it } from "vitest";
import { checkAnswer, supportsInput } from "./answer";
import type { Goal } from "../types/generated/puzzle";

const goal = (over: Partial<Goal> = {}): Goal => ({
  fact: "aconst:a:b:b:c=1/9",
  question: "∠ABC",
  quantity: { kind: "angle", at: ["A", "B", "C"] },
  answer: { exact: "20", approx: 20, display: "20°" },
  input: { mode: "keypad", exactness: "integer", unit: "deg", tolerance: null },
  ...over,
});

describe("integer answers", () => {
  it("accepts the exact value", () => {
    expect(checkAnswer(goal(), "20")).toBe("correct");
  });

  it("rejects a near miss", () => {
    expect(checkAnswer(goal(), "21")).toBe("wrong");
    expect(checkAnswer(goal(), "19")).toBe("wrong");
  });

  it("rejects a decimal that rounds to the answer", () => {
    // An integer goal means an integer answer. Accepting 20.4 would be scoring a different
    // question from the one the bank asked.
    expect(checkAnswer(goal(), "20.4")).toBe("wrong");
  });

  it("ignores surrounding space but not stray characters", () => {
    expect(checkAnswer(goal(), " 20 ")).toBe("correct");
    expect(checkAnswer(goal(), "20°")).toBe("wrong");
  });

  it("reports an empty entry as empty, not wrong", () => {
    // A wrong verdict would increment the attempt counter for pressing Check on nothing.
    expect(checkAnswer(goal(), "")).toBe("empty");
    expect(checkAnswer(goal(), "   ")).toBe("empty");
  });
});

describe("decimal answers", () => {
  const decimal = goal({
    answer: { exact: "45/2", approx: 22.5, display: "22.5°" },
    input: { mode: "keypad", exactness: "decimal", unit: "deg", tolerance: 0.05 },
  });

  it("accepts inside the puzzle's tolerance and refuses outside it", () => {
    expect(checkAnswer(decimal, "22.5")).toBe("correct");
    expect(checkAnswer(decimal, "22.54")).toBe("correct");
    expect(checkAnswer(decimal, "22.6")).toBe("wrong");
  });

  it("treats a missing tolerance as exact rather than as permissive", () => {
    const strict = goal({
      answer: { exact: "45/2", approx: 22.5, display: "22.5°" },
      input: { mode: "keypad", exactness: "decimal", unit: "deg", tolerance: null },
    });
    expect(checkAnswer(strict, "22.5")).toBe("correct");
    expect(checkAnswer(strict, "22.51")).toBe("wrong");
  });
});

describe("unsupported input modes", () => {
  const fraction = goal({
    input: { mode: "keypad", exactness: "fraction", unit: "", tolerance: null },
  });

  it("says so instead of guessing", () => {
    // No v1 bank contains one — `angle` is the only registered quantity type (docs/09). This
    // is the guard that stops a P3 bank being silently marked wrong by an input that cannot
    // express its answers.
    expect(supportsInput(fraction)).toBe(false);
    expect(checkAnswer(fraction, "1/2")).toBe("unsupported");
  });

  it("refuses a mode it has no widget for", () => {
    expect(supportsInput(goal({ input: { ...goal().input, mode: "slider" } }))).toBe(false);
  });
});
