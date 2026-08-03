import { useState } from "react";
import { Figure } from "../render/Figure";
import { Solution } from "../player/Solution";
import type { PlayerState } from "../player/state";
import { fill, strings } from "../strings/en";
import type { Outcome } from "../store/local";
import type { Puzzle } from "../types/generated/puzzle";

export interface CompleteScreenProps {
  puzzle: Puzzle;
  outcome: Outcome;
  result: PlayerState;
  showLabels: boolean;
  onNext: () => void;
  onHome: () => void;
}

const VERDICT: Record<Outcome, string> = {
  solved: strings.complete.solved,
  assisted: strings.complete.assisted,
  revealed: strings.complete.revealed,
};

export function CompleteScreen({
  puzzle,
  outcome,
  result,
  showLabels,
  onNext,
  onHome,
}: CompleteScreenProps) {
  // A replay is opt-in: someone who solved it unaided may not want the answer explained.
  const [replaying, setReplaying] = useState(outcome === "revealed");
  const [focusedStep, setFocusedStep] = useState<number | null>(null);

  const highlights =
    focusedStep === null ? [] : (puzzle.solution[focusedStep]?.highlights ?? []);

  return (
    <div className="screen complete-screen">
      <header className="bar">
        <button type="button" className="bar-button" onClick={onHome}>
          {strings.complete.home}
        </button>
        <span className="bar-title">{VERDICT[outcome]}</span>
        <span className="bar-spacer" />
      </header>

      <div className="figure-frame">
        <Figure
          figure={puzzle.figure}
          highlights={highlights}
          showLabels={showLabels}
          title={fill(strings.figure.label, { question: puzzle.goal.question })}
        />
      </div>

      <div className="complete-body">
        <p className="finish-answer">
          {fill(strings.complete.answerWas, { answer: puzzle.goal.answer.display })}
        </p>

        <dl className="tally">
          <div>
            <dt>{strings.complete.attempts}</dt>
            <dd>{result.attempts}</dd>
          </div>
          <div>
            <dt>{strings.complete.hintsUsed}</dt>
            <dd>
              {result.hintsShown} / {puzzle.solution.length}
            </dd>
          </div>
        </dl>

        <button
          type="button"
          className="secondary"
          aria-expanded={replaying}
          onClick={() => setReplaying((on) => !on)}
        >
          {replaying ? strings.complete.replayHide : strings.complete.replay}
        </button>

        {replaying && (
          <Solution
            steps={puzzle.solution}
            shown={puzzle.solution.length}
            focused={focusedStep}
            onFocus={setFocusedStep}
          />
        )}

        <button type="button" className="primary" onClick={onNext}>
          {strings.complete.next}
        </button>
      </div>
    </div>
  );
}
