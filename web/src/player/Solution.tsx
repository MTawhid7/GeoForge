// The solution list — hints and replay are the same component at different reveal counts.
//
// Steps render **verbatim** (docs/06 §6.2): text from the bank, order from the bank, and the
// highlights are the ids the bank attached to that step. The frontend never re-derives, never
// re-orders and never rewrites a sentence. That is why hints and replay can share one list:
// a hint is the first n steps, a replay is all of them.

import { fill, strings } from "../strings/en";
import type { Step } from "../types/generated/puzzle";

export interface SolutionProps {
  steps: readonly Step[];
  /** How many are visible. */
  shown: number;
  /** The step whose highlights are on the figure, or null. */
  focused: number | null;
  onFocus: (index: number | null) => void;
}

export function Solution({ steps, shown, focused, onFocus }: SolutionProps) {
  if (shown === 0) return null;
  return (
    <ol className="solution" aria-label={strings.complete.replay}>
      {steps.slice(0, shown).map((step, index) => (
        <li key={step.step} className={`solution-step${focused === index ? " is-focused" : ""}`}>
          <button
            type="button"
            className="solution-button"
            aria-pressed={focused === index}
            onClick={() => onFocus(focused === index ? null : index)}
          >
            <span className="solution-index">
              {fill(strings.complete.step, { n: step.step })}
            </span>
            <span className="solution-text">{step.text}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}
