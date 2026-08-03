# web/ — the GeoForge frontend

A static React/TypeScript app that renders a validated puzzle bank. It contains **no geometry
logic**: every fact, every figure coordinate and every sentence of every solution is decided by
the offline pipeline and shipped in the JSON (docs/02 invariant 1, docs/06).

## Running it

```bash
make bank          # from the repo root — builds banks/v2
npm run dev        # copies that bank into public/ and starts vite
```

`npm run dev` fails loudly if there is no bank to serve, because an app with an empty bank looks
like a broken app.

```bash
npm run test       # vitest + testing-library
npm run e2e        # playwright, against the committed fixture bank
npm run build      # tsc -b && vite build
npm run lint
```

## Where things are

| | |
|---|---|
| `src/types/generated/` | **Generated** from `src/geoforge/schema.py`. Never edit; `make typecheck` fails on drift. |
| `src/render/` | The figure: points, segments, circles, marks, highlights. `geometry.ts` turns coordinates into path data and decides nothing. |
| `src/player/` | Answer checking, the hint/attempt state machine, and the widgets around them. `answer.ts` and `state.ts` are pure. |
| `src/screens/` | Home, Player, Complete, Settings — the four screens of docs/06 §6.1. |
| `src/store/` | Versioned localStorage. No accounts, no analytics, no state library. |
| `src/strings/` | The UI string table. A test parses every component and fails on a literal. |
| `fixtures/bank/` | A committed subset of a real build. Regenerate with `npm run bank:fixture`'s source script after a schema change. |

## Two things worth knowing before changing the renderer

**Highlight ids are compared canonically, not as strings.** `seg:A:B` and `seg:B:A` are one
segment; `angle:P:V:Q` and `angle:Q:V:P` are one angle — but `angle:B:A:C` and `angle:A:B:C` are
two, because they have different vertices. `highlightKey` in `src/render/ids.ts` is the only
place that knows this, and sorting all three labels of an angle is the bug it exists to prevent.

**The bank is fetched, not bundled.** The manifest comes first and shards load per band, which
is what the lazy-loading test asserts. Importing the bank as a module would compile it into the
bundle and quietly delete that property.
