"""Fixture corpus for the SAL contract suite."""

from __future__ import annotations

from geoforge.solvers import ProblemSpec

# Fixture corpus. Every backend must satisfy the contract on all of these.
# Drawn from the Phase 0 spike set (spikes/p0/problems/spike_problems.txt), which was itself
# built from Newclid's own datasets, so the JGEX syntax is known-good.
CORPUS: dict[str, ProblemSpec] = {
    "thales_semicircle": ProblemSpec(
        construction="a b = segment a b; o = midpoint o a b; c = on_circle c o a",
        goals=("aconst a c c b 1pi/2",),
    ),
    "eq_triangle_60": ProblemSpec(
        construction="b c = segment b c; a = eq_triangle a b c",
        goals=("aconst a b a c 1pi/3",),
    ),
    "circum_right_angle": ProblemSpec(
        construction=(
            "a b = segment a b; c = on_tline c b a b, eqdistance c b a b; "
            "d = on_circum d a b c, eqdistance d c a b"
        ),
        goals=("aconst d a a b 1pi/2",),
    ),
    "angle_chain_5": ProblemSpec(
        construction=(
            "a b = segment a b; c = s_angle a b c 1o; d = s_angle b c d 1o; "
            "e = s_angle c d e 1o; f = s_angle d e f 1o; g = s_angle e f g 1o"
        ),
        goals=("aconst a b f g 5o",),
    ),
    # Langley-class: the classic statement needs an auxiliary line, so the fixture includes
    # it in the construction. Forward chaining then suffices (docs/07 L1).
    "langley_with_auxiliary": ProblemSpec(
        construction=(
            "a b = segment a b; c = s_angle a b c 150o, s_angle b a c 30o; "
            "d = s_angle c a d 20o, on_line d c b"
        ),
        goals=("aconst a d b c 5pi/9",),
    ),
}

#: Constructions with no goal, used to exercise saturation mode.
SATURATION_CORPUS: dict[str, ProblemSpec] = {
    "triangle_circum": ProblemSpec(
        construction="a b c = triangle a b c; o = circle o a b c; d = on_circum d a b c"
    ),
    "midpoint_circle": ProblemSpec(
        construction="a b = segment a b; o = midpoint o a b; c = on_circle c o a"
    ),
}
