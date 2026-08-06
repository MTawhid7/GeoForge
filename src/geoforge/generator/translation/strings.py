"""The rule → text string table (docs/02 localization decision, docs/03 §3.5 item 4).

Solution text is **pre-rendered at bank-build time** from this table; the frontend never composes
sentences. Translating the app means rebuilding banks per locale (docs/07 T4), so a new locale is a
new table here and nothing else.

`TEMPLATE_ID`s are **public API** — they appear in puzzle JSON as `solution[].rule` (CLAUDE.md).
Renaming one is a schema change, not a refactor.

Placeholders are `{premises}` (the step's stated premises, already rendered and joined) and
`{conclusion}`. A template may use either or both.
"""

from __future__ import annotations

#: English solution-step templates, keyed by template id.
EN: dict[str, str] = {
    # Triangles
    "isosceles_base_angles": "{premises}, so the base angles are equal: {conclusion}.",
    "equal_base_angles_isosceles": "{premises}, so the triangle is isosceles: {conclusion}.",
    "similar_triangles_properties": "Since {premises}, corresponding parts give {conclusion}.",
    "aa_similarity": "{premises}, so {conclusion} (two pairs of equal angles).",
    "sas_similarity": "{premises}, so {conclusion} "
    "(two sides in ratio with equal included angles).",
    "sss_similarity": "{premises}, so {conclusion} (three sides in the same ratio).",
    "congruent_triangles_properties": "Since {premises}, matching parts are equal: {conclusion}.",
    "angle_bisector": "{premises}, so the bisector divides the opposite side in that ratio: "
    "{conclusion}.",
    # Circles
    "angles_in_same_arc": "{premises}, and angles subtending the same arc are equal, "
    "so {conclusion}.",
    "equal_angles_imply_cyclic": "{premises}, so the four points are concyclic: {conclusion}.",
    "circle_radii_equal": "{premises}, so radii of that circle are equal: {conclusion}.",
    "thales_semicircle": "{premises}, so the angle in a semicircle is a right angle: {conclusion}.",
    # Segments
    "midpoint_halves": "{premises}, so {conclusion}.",
    "midpoint_definition": "{premises}, so {conclusion}.",
    # Area (docs/10 A4). The two ratio rules name the insight rather than the arithmetic,
    # because the arithmetic is the easy half — "a median halves the area" is the step a
    # solver either sees or does not.
    "area_right_triangle": "{premises}, so the area is half the product of the legs: "
    "{conclusion}.",
    "area_heron": "{premises}, so Heron's formula gives {conclusion}.",
    "area_sas": "{premises}, so the area is half the product of the two sides and the sine of "
    "the angle between them: {conclusion}.",
    "area_median_split": "{premises}, and a median divides a triangle into two of equal area, "
    "so {conclusion}.",
    "area_cevian_split": "{premises}, and triangles on the same base have areas in the ratio of "
    "their heights, so {conclusion}.",
    # Algebraic reasoning (docs/03 §3.5 item 2)
    "combine": "Combining {premises}, we get {conclusion}.",
    "restate": "From {premises} it follows that {conclusion}.",
}
