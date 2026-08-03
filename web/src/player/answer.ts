// Checking a typed answer against `goal.input` (docs/02, docs/06 §6.2).
//
// Pure, and the only place the app compares anything to the answer. It never re-derives: the
// bank states both the exact value and its decimal, cross-validated by a second engine, and
// this reads them.
//
// v1 registers `angle` only, whose answers are whole degrees (docs/09), so `integer` is the
// mode every shipped puzzle uses. `decimal` is implemented alongside it because it is the same
// comparison with a tolerance. `fraction` is *not*: it needs a two-field p/q keypad, and
// building an input for data that will not exist until P3 registers `ratio` would ship an
// untested path. It returns `unsupported` — loudly, so a future bank cannot slip past it.

import type { Goal } from "../types/generated/puzzle";

export type Verdict = "correct" | "wrong" | "unsupported" | "empty";

export function supportsInput(goal: Goal): boolean {
  return (
    goal.input.mode === "keypad" &&
    (goal.input.exactness === "integer" || goal.input.exactness === "decimal")
  );
}

export function checkAnswer(goal: Goal, entry: string): Verdict {
  const text = entry.trim();
  if (text === "") return "empty";
  if (!supportsInput(goal)) return "unsupported";

  const typed = Number(text);
  if (!Number.isFinite(typed)) return "wrong";

  if (goal.input.exactness === "integer") {
    if (!/^-?\d+$/.test(text)) return "wrong";
    // Compare against `exact`, not `approx`: `approx` is a rounded float and the exact string
    // is what the validator agreed on.
    return typed === Number(goal.answer.exact) ? "correct" : "wrong";
  }

  // `decimal`: the tolerance is the puzzle's, and a bank that omits one means "exact".
  const tolerance = goal.input.tolerance ?? 0;
  return Math.abs(typed - goal.answer.approx) <= tolerance ? "correct" : "wrong";
}

/** Whether a decimal point can be typed. Integer answers refuse it rather than round it away. */
export const allowsDecimalPoint = (goal: Goal): boolean => goal.input.exactness === "decimal";

/** Longest sensible entry, so the field cannot be filled with digits until it overflows. */
export const MAX_ENTRY = 8;
