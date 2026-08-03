# 06 — Frontend and UX

The frontend is deliberately thin: it renders validated JSON. All geometric truth is decided offline.
Design language: clean, minimal, Euclidea-like; the figure is the hero; text minimal (audience includes
non-native English speakers — symbols and highlighting over prose).

## 6.1 Screens (v1)

1. **Home:** daily puzzle card + practice entry per band + streak counter (localStorage; no accounts).
2. **Puzzle player** (core screen, below).
3. **Puzzle complete:** confirmation, solution replay, next puzzle.
4. **Settings:** theme, angle-input mode, reset local data.

## 6.2 Puzzle player

- **Figure:** SVG, centered, scales to viewport (fully usable at 360 px). Given angles as arc marks with
  degree labels; given lengths as segment labels; equal segments with ticks; parallels with arrows;
  right angles with squares; shaded regions as translucent fills. The **goal mark is per quantity type**:
  highlighted arc + "?" (angle), highlighted segment/brace + "?" (length), the two segments highlighted
  + "?:?" (ratio), pulsing shaded region + "?" (area).
- **Answer input (driven by `goal.input`, doc 02):** `integer` → numeric keypad (angles); `fraction` →
  two-field p/q keypad (ratios); `decimal` → keypad with decimal point, checked against `approx` within
  the puzzle's tolerance, exact form (`3√2`) shown on solve (lengths/areas). Wrong answers shake +
  increment attempt counter; no reveal until solved or give-up.
- **Interaction:** tap element to highlight; pinch-zoom/pan; no point dragging (static figure in v1).
  Pan and zoom are the browser's own — the viewport meta deliberately does not disable user scaling,
  so no gesture code is carried for something the platform already does correctly.
- **Layout (settled Phase 2 M2):** the figure is **sticky** on narrow screens. Measured on the built
  app: the givens, the entry field and four keypad rows put *Check* about 150 px below the fold on a
  390×844 phone and do not fit a 360×640 screen at any size. Shrinking the figure until everything
  fits makes the figure unreadable, so instead it follows the page down — which is what you want
  anyway, since the figure is what you are reasoning about while typing. Above 48 rem it is static.
- **Hints:** reveal solution steps one at a time (text + element highlights, derivation order). All hints
  taken ⇒ marked "assisted", not solved. Read literally: *all*, so two hints out of five and then a
  correct answer is a solve. `hintsShown` is stored alongside the outcome either way, so a stricter
  rule can be adopted later without rewriting what past results meant.
- **Solution replay:** steps from the JSON verbatim (`derives`, `highlights` — grammar in doc 02); the
  frontend never re-derives or re-orders anything.

## 6.3 Diagram layout (offline, `bank/layout.py` — not the frontend)

1. **Display instantiation:** optimize over remaining free parameters — maximize minimum point distance
   and feature angles, aspect ratio near 4:3, penalize label-collision risk. (Architecture reference:
   `penrose/` — constraint-based layout via numerical optimization; we keep our own small implementation.)
2. **Anti-leak perturbation:** the figure must not visually assert facts absent from the premises:
   undeclared equal-looking segments must differ ≥ 8% in display; undeclared near-parallels ≥ 6° apart;
   undeclared near-right angles ≥ 6° from 90°. Whether a near-fact is *forced* is decided symbolically —
   ask the SAL whether the closure derives it; if derivable, it's genuinely implied: accept and log. If
   not derivable and the optimizer cannot separate it, discard the layout attempt and log (an optimizer
   failure is not evidence of forcedness). **Never perturb declared facts**: figures are always metrically
   consistent with all premises; no "not to scale" figures (consequence: doc 07 T5).
3. **Label placement:** repulsion pass for point labels; angle labels inside the arc where wide enough,
   leader lines otherwise. The offset *direction* is chosen here and shipped in the JSON; its
   *magnitude* (`LAYOUT.label_radius`) is calibrated against the renderer's font size, because only
   the renderer knows how big a label is. It was 16 viewbox units against a 34-unit glyph until the
   frontend was first drawn — the label sat on top of its own point.
4. Output: final coordinates + label offsets in the JSON. The frontend does no layout beyond viewport
   scaling.

## 6.4 Accessibility & i18n

- All step text is generated at bank build from the rule→template string table; banks are per-locale
  (v1: English). No strings hardcoded in components; UI chrome uses the frontend string table.
- Color-vision safety: highlights use color + thickness + dash, never color alone.
- Marks meet minimum stroke/size at 360 px width.

## 6.5 Frontend engineering constraints

- React + TypeScript + Vite; SVG via plain JSX; no geometry/chart libraries.
- **Where "no geometry logic" ends.** The renderer reads coordinates and emits path data — an arc
  mark at `at: [P, V, Q]` cannot be drawn without knowing which way the two rays point, exactly as a
  segment cannot be drawn without reading two points. What it never does is decide, derive, check or
  reorder a geometric fact: every fact the figure shows was settled offline and arrives in the JSON.
- Puzzle JSON types **generated** from the schema (CI drift check). The bank *manifest* is
  generated too (`schema.Manifest` → `bank-<v>.schema.json` + the same TS file): the frontend
  reads it before anything else, so it is part of the contract. The layout viewbox ships as a
  generated `VIEWBOX` constant rather than being agreed by convention — deriving it from the
  points in the client would put framing, a §6.3 layout decision, back in the client.
- State: component state + thin localStorage module (`stats`, `settings`, `seenPuzzles`); no state
  library without documented need.
- Bank ships as per-band lazy-loaded shards + manifest; first puzzle interactive < 2 s on a mid-range
  phone over 3G-fast.
- No analytics/tracking in v1 beyond localStorage.
