// The UI string table (docs/06 §6.4). Nothing user-visible is written in a component.
//
// This is not premature i18n: puzzle text is already generated per locale at bank build, so a
// second locale means a bank plus this file — and a component with a literal in it is the one
// thing that would not be covered. `noHardcodedStrings.test.ts` enforces that.

export const strings = {
  app: {
    name: "GeoForge",
    tagline: "Geometry puzzles with worked solutions.",
  },
  nav: {
    home: "Home",
    settings: "Settings",
    back: "Back",
    close: "Close",
  },
  home: {
    daily: "Today's puzzle",
    dailyDone: "Solved today",
    dailyAssisted: "Solved with hints",
    practice: "Practice",
    streak: "Day streak",
    streakBest: "Best",
    solvedCount: "Solved",
    play: "Play",
    resume: "Resume",
    bandProgress: "{solved} of {total}",
    bandEmpty: "None yet",
    noBand: "No puzzles in this band.",
  },
  bands: {
    easy: "Easy",
    medium: "Medium",
    hard: "Hard",
    expert: "Expert",
  },
  player: {
    given: "Given",
    find: "Find",
    yourAnswer: "Your answer",
    submit: "Check",
    clear: "Clear",
    backspace: "Delete",
    degrees: "degrees",
    hint: "Hint",
    hintCount: "Hint {n} of {total}",
    hintsExhausted: "All hints shown",
    giveUp: "Show solution",
    attempts: "{n} attempts",
    attemptsOne: "1 attempt",
    wrong: "Not quite.",
    correct: "Correct.",
    depth: "{n} steps",
    tapToHighlight: "Tap a given to highlight it",
  },
  complete: {
    solved: "Solved",
    assisted: "Solved with hints",
    revealed: "Solution shown",
    answerWas: "The answer is {answer}.",
    replay: "Walk through the solution",
    replayHide: "Hide the solution",
    step: "Step {n}",
    next: "Next puzzle",
    home: "Back to home",
    attempts: "Attempts",
    hintsUsed: "Hints used",
  },
  settings: {
    title: "Settings",
    theme: "Theme",
    themeSystem: "System",
    themeLight: "Light",
    themeDark: "Dark",
    labels: "Point labels",
    labelsOn: "Show",
    labelsOff: "Hide",
    reset: "Reset local data",
    resetHint: "Clears your streak, solved puzzles and settings on this device.",
    resetConfirm: "Reset everything?",
    resetDone: "Local data cleared.",
    about: "About this bank",
    bankSeed: "Seed",
    bankPuzzles: "Puzzles",
    bankEngines: "Engines",
    bankGenerator: "Generator",
    bankPreview: "Preview bank — not shippable",
    bankMissing: "Still missing: {list}",
  },
  status: {
    loading: "Loading…",
    bankMissing: "No puzzle bank found.",
    bankMissingHint: "Run `make bank` from the repo root, then `npm run bank:dev`.",
    bankUnreadable: "This bank was built for a newer version of the app.",
    retry: "Try again",
  },
  figure: {
    label: "Figure for {question}",
    goalMark: "The angle to find is marked with a question mark.",
  },
} as const;

/** Fill `{name}` placeholders. Absent keys are left as-is so a typo is visible, not silent. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (whole, key: string) =>
    key in values ? String(values[key]) : whole,
  );
}
