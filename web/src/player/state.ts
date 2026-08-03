// The player's state machine, as a pure reducer.
//
// Pure because these are the rules that decide what counts as solving a puzzle, and rules
// worth stating are rules worth testing without a DOM.
//
// **"Assisted" means every hint was taken.** docs/06 §6.2 says "all hints taken ⇒ marked
// assisted, not solved" — so taking two hints out of five and then solving it is a solve. That
// is the doc read literally, and it is the lenient reading; `hintsShown` is recorded either
// way, so the stricter rule stays available without changing what past results meant.

import { MAX_ENTRY, allowsDecimalPoint, checkAnswer } from "./answer";
import type { Verdict } from "./answer";
import type { Goal } from "../types/generated/puzzle";

export type Status = "playing" | "solved" | "assisted" | "revealed";

export interface PlayerState {
  entry: string;
  attempts: number;
  hintsShown: number;
  status: Status;
  /** Last verdict, for the message under the field. */
  verdict: Verdict | null;
  /** Bumped on every wrong answer so the shake animation restarts (docs/06 §6.2). */
  shake: number;
}

export type PlayerAction =
  | { type: "digit"; value: string }
  | { type: "backspace" }
  | { type: "clear" }
  | { type: "submit" }
  | { type: "hint" }
  | { type: "reveal" };

export const initialState: PlayerState = {
  entry: "",
  attempts: 0,
  hintsShown: 0,
  status: "playing",
  verdict: null,
  shake: 0,
};

export interface PlayerRules {
  goal: Goal;
  /** How many solution steps exist — the hint budget. */
  steps: number;
}

export function reduce(state: PlayerState, action: PlayerAction, rules: PlayerRules): PlayerState {
  if (state.status !== "playing" && action.type !== "hint") return state;

  switch (action.type) {
    case "digit": {
      if (action.value === "." && !allowsDecimalPoint(rules.goal)) return state;
      if (action.value === "." && state.entry.includes(".")) return state;
      if (state.entry.length >= MAX_ENTRY) return state;
      return { ...state, entry: state.entry + action.value, verdict: null };
    }
    case "backspace":
      return { ...state, entry: state.entry.slice(0, -1), verdict: null };
    case "clear":
      return { ...state, entry: "", verdict: null };
    case "submit": {
      const verdict = checkAnswer(rules.goal, state.entry);
      if (verdict === "empty" || verdict === "unsupported") return { ...state, verdict };
      if (verdict === "wrong") {
        return {
          ...state,
          verdict,
          attempts: state.attempts + 1,
          shake: state.shake + 1,
          entry: "",
        };
      }
      return {
        ...state,
        verdict,
        attempts: state.attempts + 1,
        status: state.hintsShown >= rules.steps ? "assisted" : "solved",
      };
    }
    case "hint": {
      if (state.hintsShown >= rules.steps) return state;
      return { ...state, hintsShown: state.hintsShown + 1 };
    }
    case "reveal":
      return { ...state, status: "revealed", hintsShown: rules.steps, entry: "" };
  }
}

export const isFinished = (state: PlayerState): boolean => state.status !== "playing";
