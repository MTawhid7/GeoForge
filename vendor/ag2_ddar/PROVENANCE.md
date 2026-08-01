# Provenance — vendored AlphaGeometry 2 DDAR

| field | value |
|---|---|
| Upstream | https://github.com/google-deepmind/alphageometry2 |
| Commit | `251e7e16f0bba8ac7c83cdea789fccc195d0c0c7` |
| Vendored on | 2026-08-01 |
| License | Apache-2.0 (see `LICENSE`, retained verbatim) |
| Modifications | **None.** Files copied verbatim. |

## Why vendored rather than depended on

The upstream repository ships no `pyproject.toml` and is not published to PyPI, so there is
no version to pin. It is small (2,394 LOC) and depends only on `numpy`, so carrying it is
cheap. See `docs/07` P1 for the dependency-policy tiers.

## Role in GeoForge

Independent cross-validator (`docs/02` invariant 3): every banked puzzle is re-derived by
this engine, whose codebase shares no lineage with the generation engine (Newclid), so a
soundness bug in one is unlikely to be mirrored in the other.

## Verified behaviour (Phase 0 smoke test)

```python
from ddar import DDAR
from parse import AGProblem
p = AGProblem.parse('a@0.0_0.0 = ; b@1.0_0.0 = ; c@0.5_0.8660254037844386 = '
                    'cong a b b c, cong b c c a ? acompute a b a c')
d = DDAR(p.points)
for pred in p.preds: d.force_pred(pred)
d.deduction_closure()
d.check_pred(p.goal)   # -> Fraction(2, 3)  i.e. 120 degrees
```

**Integration caveat (found in Phase 0):** DDAR's directed-angle orientation is the OPPOSITE
of Newclid's. The same equilateral configuration that Newclid reports as one value, DDAR
reports as its supplement. The cross-validator MUST calibrate the convention (θ vs 180−θ)
before comparing, or it will report a false soundness failure on every puzzle.

Coordinates are mandatory in DDAR problem strings (`name@x_y`) and premises are asserted
numerically to ~1e-6, so the exporter must emit the exact solver coordinates.
