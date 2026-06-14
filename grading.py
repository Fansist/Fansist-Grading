"""grading.py

Map raw measurements to sub-grades and assemble a full card grade.

This now grades all FOUR factors:
  * centering -- from the L:R / T:B ratios (``centering.py``).
  * corners   -- from a corner-wear score (``corners.py``).
  * edges     -- from an edge-wear score (``edges.py``).
  * surface   -- from a surface-defect score (``surface.py``).

Each factor has its own plain, easy-to-edit threshold table (loosely modelled on
hobby grading scales). The overall grade is combined from whichever sub-scores
are present via :func:`compute_overall`, with a selectable strategy
(weighted / lowest / average). A sub-score left as ``None`` is simply omitted,
so the schema and combiner are unchanged whether you grade one factor or all
four. Tune all the numbers below to match the grading standard you care about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Centering grade scale (easy to edit)
# ---------------------------------------------------------------------------
#
# Centering is judged by the WORSE of the two axes, expressed as the larger
# side's percentage (e.g. a 55/45 card has a "worse %" of 55). Smaller is
# better; a perfectly centered card is 50.
#
# Each row is (max_worse_percent, grade_value, label). The first row whose
# threshold the card meets (worse_percent <= max_worse_percent) wins, so keep
# the table ordered from best (tightest) to worst.
CENTERING_GRADE_SCALE: list[tuple[float, float, str]] = [
    (55.0, 10.0, "Gem Mint"),     # ~50/50 .. 55/45
    (60.0, 9.0, "Mint"),          # up to 60/40
    (65.0, 8.0, "NM-MT"),         # up to 65/35
    (70.0, 7.0, "Near Mint"),     # up to 70/30
    (75.0, 6.0, "EX-MT"),         # up to 75/25
    (80.0, 5.0, "Excellent"),     # up to 80/20
    (85.0, 4.0, "VG-EX"),         # up to 85/15
    (90.0, 3.0, "Very Good"),     # up to 90/10
    (100.0, 1.0, "Poor"),         # anything worse
]

# Fallback grade/label if (somehow) nothing in the scale matches. The scale's
# last row covers up to 100, so this should never trigger in practice.
_WORST_GRADE: tuple[float, str] = (1.0, "Poor")

# ---------------------------------------------------------------------------
# Condition (corners / edges / surface) grade scales
# ---------------------------------------------------------------------------
#
# Corners, edges and surface each produce a "wear" / "defect" score in [0, 1]
# (0 = pristine, 1 = worst). Each row is (max_wear, grade_value, label); the
# first row whose threshold the card meets (wear <= max_wear) wins, so keep the
# tables ordered from best (cleanest) to worst.
#
# They are SEPARATE tables (even though they start identical) so each factor can
# be tuned independently -- e.g. surface tolerance is usually the flakiest.
CORNER_GRADE_SCALE: list[tuple[float, float, str]] = [
    (0.02, 10.0, "Gem Mint"),
    (0.05, 9.0, "Mint"),
    (0.10, 8.0, "NM-MT"),
    (0.18, 7.0, "Near Mint"),
    (0.28, 6.0, "EX-MT"),
    (0.40, 5.0, "Excellent"),
    (0.55, 4.0, "VG-EX"),
    (0.75, 3.0, "Very Good"),
    (1.01, 1.0, "Poor"),
]
EDGE_GRADE_SCALE: list[tuple[float, float, str]] = list(CORNER_GRADE_SCALE)
SURFACE_GRADE_SCALE: list[tuple[float, float, str]] = list(CORNER_GRADE_SCALE)

# ---------------------------------------------------------------------------
# Overall-grade combination
# ---------------------------------------------------------------------------
#
# How to combine the present sub-grades into an overall:
#   "weighted" -- weighted mean using OVERALL_WEIGHTS (default).
#   "lowest"   -- the single worst sub-grade governs (conservative, PSA-ish).
#   "average"  -- plain mean of present sub-grades.
OVERALL_STRATEGY: str = "weighted"

# Weights for the "weighted" strategy. Only the present sub-scores' weights are
# used (renormalised), so this is correct whether 1 or 4 factors are graded.
OVERALL_WEIGHTS: dict[str, float] = {
    "centering": 0.20,
    "corners": 0.30,
    "edges": 0.20,
    "surface": 0.30,
}


@dataclass
class CardGrade:
    """A full card grade: four sub-grades plus a combined overall.

    Attributes:
        centering_ratio_h: (left%, right%) horizontal centering, summing to 100.
        centering_ratio_v: (top%, bottom%) vertical centering, summing to 100.
        centering_grade / centering_label: centering sub-grade + label.
        corners / edges / surface: condition sub-grades (``None`` if a factor was
            not assessed); each has a matching ``*_label``.
        overall: Combined grade computed from the present sub-scores.
    """

    centering_ratio_h: tuple[float, float]
    centering_ratio_v: tuple[float, float]
    centering_grade: float
    centering_label: str = ""

    # --- Condition sub-grades (None if that factor was not assessed) ---------
    corners: Optional[float] = None
    corners_label: str = ""
    edges: Optional[float] = None
    edges_label: str = ""
    surface: Optional[float] = None
    surface_label: str = ""

    overall: Optional[float] = field(default=None)

    def sub_scores(self) -> dict[str, Optional[float]]:
        """All sub-scores by name (``None`` where a factor wasn't assessed)."""
        return {
            "centering": self.centering_grade,
            "corners": self.corners,
            "edges": self.edges,
            "surface": self.surface,
        }

    def to_dict(self) -> dict:
        """Plain-dict view of the grade for JSON output (UI, CLI, traceability)."""
        return {
            "centering_ratio_h": list(self.centering_ratio_h),
            "centering_ratio_v": list(self.centering_ratio_v),
            "centering_grade": self.centering_grade,
            "centering_label": self.centering_label,
            "corners": self.corners,
            "corners_label": self.corners_label,
            "edges": self.edges,
            "edges_label": self.edges_label,
            "surface": self.surface,
            "surface_label": self.surface_label,
            "overall": self.overall,
        }


def worse_centering_percent(
    horizontal_ratio: tuple[float, float],
    vertical_ratio: tuple[float, float],
) -> float:
    """Return the worst (largest) side-percentage across both axes.

    This single number drives the centering grade: 50 is perfect, higher is
    worse. e.g. ratios (58, 42) and (52, 48) -> 58.
    """
    return max(max(horizontal_ratio), max(vertical_ratio))


def grade_centering(
    horizontal_ratio: tuple[float, float],
    vertical_ratio: tuple[float, float],
) -> tuple[float, str]:
    """Map centering ratios to a (grade_value, label) using the scale table."""
    worse = worse_centering_percent(horizontal_ratio, vertical_ratio)
    for max_worse, grade_value, label in CENTERING_GRADE_SCALE:
        if worse <= max_worse:
            return grade_value, label
    return _WORST_GRADE


def _grade_from_wear(
    wear: float, scale: list[tuple[float, float, str]]
) -> tuple[float, str]:
    """Map a [0, 1] wear/defect score to (grade_value, label) via a scale table."""
    for max_wear, grade_value, label in scale:
        if wear <= max_wear:
            return grade_value, label
    return _WORST_GRADE


def grade_corners(wear: float) -> tuple[float, str]:
    """Map a corner-wear score (0=pristine..1=worst) to (grade, label)."""
    return _grade_from_wear(wear, CORNER_GRADE_SCALE)


def grade_edges(wear: float) -> tuple[float, str]:
    """Map an edge-wear score (0=pristine..1=worst) to (grade, label)."""
    return _grade_from_wear(wear, EDGE_GRADE_SCALE)


def grade_surface(wear: float) -> tuple[float, str]:
    """Map a surface-defect score (0=clean..1=worst) to (grade, label)."""
    return _grade_from_wear(wear, SURFACE_GRADE_SCALE)


def _round_half(value: float) -> float:
    """Round to the nearest 0.5 (grades are usually whole or half steps)."""
    return round(value * 2.0) / 2.0


def compute_overall(
    sub_scores: dict[str, Optional[float]],
    strategy: Optional[str] = None,
) -> Optional[float]:
    """Combine the present sub-scores into an overall grade.

    Only sub-scores that are not ``None`` are considered, so this is correct
    whether one factor or all four are graded (a card with only centering simply
    returns the centering grade). The ``strategy`` (default ``OVERALL_STRATEGY``)
    selects how present sub-scores combine: ``"weighted"`` / ``"lowest"`` /
    ``"average"``. Result is rounded to the nearest 0.5.
    """
    strategy = strategy or OVERALL_STRATEGY
    present = {name: score for name, score in sub_scores.items() if score is not None}
    if not present:
        return None
    values = list(present.values())

    if strategy == "lowest":
        raw = min(values)
    elif strategy == "average":
        raw = sum(values) / len(values)
    elif strategy == "weighted":
        weights = {name: OVERALL_WEIGHTS.get(name, 0.0) for name in present}
        total_w = sum(weights.values())
        if total_w <= 0:  # no configured weights -> fall back to a plain mean
            raw = sum(values) / len(values)
        else:
            raw = sum(present[name] * weights[name] for name in present) / total_w
    else:
        raise ValueError(
            f"Unknown overall strategy {strategy!r}; expected "
            "'weighted', 'lowest', or 'average'."
        )
    return _round_half(raw)


def build_full_grade(
    horizontal_ratio: tuple[float, float],
    vertical_ratio: tuple[float, float],
    corner_wear: Optional[float] = None,
    edge_wear: Optional[float] = None,
    surface_wear: Optional[float] = None,
    overall_strategy: Optional[str] = None,
) -> CardGrade:
    """Build a full :class:`CardGrade` from centering + condition wear scores.

    Any of the condition wear scores may be ``None`` (that factor not assessed),
    in which case its sub-grade stays ``None`` and is left out of the overall.
    """
    centering_grade, centering_label = grade_centering(horizontal_ratio, vertical_ratio)

    grade = CardGrade(
        centering_ratio_h=horizontal_ratio,
        centering_ratio_v=vertical_ratio,
        centering_grade=centering_grade,
        centering_label=centering_label,
    )
    if corner_wear is not None:
        grade.corners, grade.corners_label = grade_corners(corner_wear)
    if edge_wear is not None:
        grade.edges, grade.edges_label = grade_edges(edge_wear)
    if surface_wear is not None:
        grade.surface, grade.surface_label = grade_surface(surface_wear)

    grade.overall = compute_overall(grade.sub_scores(), strategy=overall_strategy)
    return grade


def build_grade(
    horizontal_ratio: tuple[float, float],
    vertical_ratio: tuple[float, float],
) -> CardGrade:
    """Build a centering-only :class:`CardGrade` (condition factors left as stubs)."""
    return build_full_grade(horizontal_ratio, vertical_ratio)
