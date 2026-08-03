import { useEffect, useMemo, useReducer, useState } from "react";
import { Figure } from "../render/Figure";
import { Givens } from "../player/Givens";
import { Keypad } from "../player/Keypad";
import { Solution } from "../player/Solution";
import { allowsDecimalPoint, supportsInput } from "../player/answer";
import { initialState, isFinished, reduce } from "../player/state";
import type { PlayerAction, PlayerState } from "../player/state";
import { fill, strings } from "../strings/en";
import type { Outcome } from "../store/local";
import type { Puzzle } from "../types/generated/puzzle";

export interface PlayerScreenProps {
  puzzle: Puzzle;
  showLabels: boolean;
  onFinish: (outcome: Outcome, state: PlayerState) => void;
  onExit: () => void;
}

const outcomeOf = (state: PlayerState): Outcome =>
  state.status === "revealed" ? "revealed" : state.status === "assisted" ? "assisted" : "solved";

export function PlayerScreen({ puzzle, showLabels, onFinish, onExit }: PlayerScreenProps) {
  const rules = useMemo(
    () => ({ goal: puzzle.goal, steps: puzzle.solution.length }),
    [puzzle],
  );
  const [state, rawDispatch] = useReducer(
    (current: PlayerState, action: PlayerAction) => reduce(current, action, rules),
    initialState,
  );
  const [focusedGiven, setFocusedGiven] = useState<number | null>(null);
  const [focusedStep, setFocusedStep] = useState<number | null>(null);
  const [pinned, setPinned] = useState<string[]>([]);

  const dispatch = (action: PlayerAction) => {
    rawDispatch(action);
    if (action.type === "submit" || action.type === "reveal") setFocusedGiven(null);
  };

  const finished = isFinished(state);
  const supported = supportsInput(puzzle.goal);

  // The complete screen is where a finished puzzle is confirmed and replayed (docs/06 §6.1),
  // so the player hands off rather than growing a second mode.
  useEffect(() => {
    if (isFinished(state)) onFinish(outcomeOf(state), state);
    // Runs on the transition into a finished status, not on every keystroke after it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.status]);

  const highlights = useMemo(() => {
    if (focusedStep !== null) return puzzle.solution[focusedStep]?.highlights ?? [];
    if (focusedGiven !== null) return puzzle.given[focusedGiven]?.highlights ?? [];
    return pinned;
  }, [focusedStep, focusedGiven, pinned, puzzle]);

  const togglePinned = (id: string) =>
    setPinned((current) => (current.includes(id) ? current.filter((x) => x !== id) : [...current, id]));

  const band = strings.bands[puzzle.difficulty.band as keyof typeof strings.bands];

  return (
    <div className="screen player-screen">
      <header className="bar">
        <button type="button" className="bar-button" onClick={onExit}>
          {strings.nav.back}
        </button>
        <span className="bar-title">
          {band} · {fill(strings.player.depth, { n: puzzle.difficulty.depth })}
        </span>
        <span className="bar-spacer" />
      </header>

      <div className="figure-frame">
        <Figure
          figure={puzzle.figure}
          highlights={highlights}
          showLabels={showLabels}
          onSelect={togglePinned}
          title={fill(strings.figure.label, { question: puzzle.goal.question })}
        />
      </div>

      <div className="player-body">
        <section className="goal" aria-live="polite">
          <h2 className="section-title">{strings.player.find}</h2>
          <p className="goal-question">{puzzle.goal.question}</p>
        </section>

        <Givens given={puzzle.given} focused={focusedGiven} onFocus={setFocusedGiven} />

        {!finished && (
          <section className="answer">
            <div
              className={`entry${state.verdict === "wrong" ? " is-wrong" : ""}`}
              key={state.shake}
              aria-label={strings.player.yourAnswer}
            >
              <span className="entry-value">{state.entry || "–"}</span>
              <span className="entry-unit">{puzzle.goal.input.unit === "deg" ? "°" : ""}</span>
            </div>
            <p className="entry-message" role="status">
              {state.verdict === "wrong" && strings.player.wrong}
              {state.verdict === "unsupported" && strings.status.bankUnreadable}
            </p>
            <Keypad
              onDigit={(value) => dispatch({ type: "digit", value })}
              onBackspace={() => dispatch({ type: "backspace" })}
              onSubmit={() => dispatch({ type: "submit" })}
              allowDecimal={allowsDecimalPoint(puzzle.goal)}
              disabled={!supported}
              canSubmit={state.entry.length > 0}
            />
            <div className="assist">
              <button
                type="button"
                className="assist-button"
                onClick={() => dispatch({ type: "hint" })}
                disabled={state.hintsShown >= puzzle.solution.length}
              >
                {state.hintsShown >= puzzle.solution.length
                  ? strings.player.hintsExhausted
                  : fill(strings.player.hintCount, {
                      n: state.hintsShown + 1,
                      total: puzzle.solution.length,
                    })}
              </button>
              <button
                type="button"
                className="assist-button assist-quiet"
                onClick={() => dispatch({ type: "reveal" })}
              >
                {strings.player.giveUp}
              </button>
            </div>
            <p className="attempts">
              {state.attempts === 1
                ? strings.player.attemptsOne
                : state.attempts > 0
                  ? fill(strings.player.attempts, { n: state.attempts })
                  : strings.player.tapToHighlight}
            </p>
          </section>
        )}

        <Solution
          steps={puzzle.solution}
          shown={state.hintsShown}
          focused={focusedStep}
          onFocus={setFocusedStep}
        />
      </div>
    </div>
  );
}
