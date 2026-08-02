"""Trace → readable solution steps (docs/03 §3.5), the pivot's hardest component.

Four things have to happen together for a machine proof to read like a solution:

* `templates`     — the curated rule whitelist; anything unlisted fails the gate.
* `idioms`        — collapsing multi-step engine idioms into single human steps.
* `vertex_angles` — directed line-to-line angles into ∠ABC, the universal conversion.
* `phrases`       — one fact, one phrase, plus its figure highlights.

`translate` runs them and applies the readability gate.
"""

from geoforge.generator.translation.translate import (
    Failure,
    FailureReason,
    SolutionStep,
    Translation,
    translate,
)

__all__ = [
    "Failure",
    "FailureReason",
    "SolutionStep",
    "Translation",
    "translate",
]
