// The given list. Tapping a given lights up the elements it names (docs/06 §6.2).
//
// `display` is the bank's sentence and `highlights` are the bank's ids — the frontend chooses
// neither. Symbols over prose is a bank-side decision too (docs/06: the audience includes
// non-native English speakers), which is why these rows are usually "AB ∥ CD" and not a clause.

import { strings } from "../strings/en";
import type { Given } from "../types/generated/puzzle";

export interface GivensProps {
  given: readonly Given[];
  /** Index of the given whose highlights are showing, or null. */
  focused: number | null;
  onFocus: (index: number | null) => void;
}

export function Givens({ given, focused, onFocus }: GivensProps) {
  return (
    <section className="givens" aria-label={strings.player.given}>
      <h2 className="section-title">{strings.player.given}</h2>
      <ul className="given-list">
        {given.map((g, index) => (
          <li key={g.fact}>
            <button
              type="button"
              className={`given-chip${focused === index ? " is-focused" : ""}`}
              aria-pressed={focused === index}
              onClick={() => onFocus(focused === index ? null : index)}
            >
              {g.display}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
