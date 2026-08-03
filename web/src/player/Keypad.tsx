import { strings } from "../strings/en";

export interface KeypadProps {
  onDigit: (value: string) => void;
  onBackspace: () => void;
  onSubmit: () => void;
  allowDecimal: boolean;
  disabled: boolean;
  canSubmit: boolean;
}

const DIGITS = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];

export function Keypad({
  onDigit,
  onBackspace,
  onSubmit,
  allowDecimal,
  disabled,
  canSubmit,
}: KeypadProps) {
  return (
    <div className="keypad" role="group" aria-label={strings.player.yourAnswer}>
      {DIGITS.map((d) => (
        <button key={d} type="button" className="key" onClick={() => onDigit(d)} disabled={disabled}>
          {d}
        </button>
      ))}
      <button
        type="button"
        className="key key-secondary"
        onClick={() => onDigit(".")}
        disabled={disabled || !allowDecimal}
        aria-hidden={!allowDecimal}
      >
        .
      </button>
      <button type="button" className="key" onClick={() => onDigit("0")} disabled={disabled}>
        0
      </button>
      <button
        type="button"
        className="key key-secondary"
        onClick={onBackspace}
        disabled={disabled}
        aria-label={strings.player.backspace}
      >
        ⌫
      </button>
      <button
        type="button"
        className="key key-submit"
        onClick={onSubmit}
        disabled={disabled || !canSubmit}
      >
        {strings.player.submit}
      </button>
    </div>
  );
}
