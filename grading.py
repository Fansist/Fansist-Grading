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


def grade_from_metric(
    value: float, scale: list[tuple[float, float, str]]
) -> tuple[float, str]:
    """Map a raw metric to (grade_value, label) via a "first row that fits" table.

    Works for any scale where smaller-is-better (wear/defect in [0,1], or the
    centering "worse %"): returns the first row whose threshold ``value`` meets.
    """
    for threshold, grade_value, label in scale:
        if value <= threshold:
            return grade_value, label
    return _WORST_GRADE


def _grade_from_wear(
    wear: float, scale: list[tuple[float, float, str]]
) -> tuple[float, str]:
    """Map a [0, 1] wear/defect score to (grade_value, label) via a scale table."""
    return grade_from_metric(wear, scale)


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


def label_for_grade(value: float, scale: list[tuple[float, float, str]]) -> str:
    """Label of the scale tier whose grade is nearest ``value``.

    Used when a *calibrated* (data-fit) grade replaces the static scale lookup,
    so the human-readable label still comes from the same tier names.
    """
    best = min(scale, key=lambda row: abs(row[1] - value))
    return best[2]


def compute_overall(
    sub_scores: dict[str, Optional[float]],
    strategy: Optional[str] = None,
    weights: Optional[dict[str, float]] = None,
) -> Optional[float]:
    """Combine the present sub-scores into an overall grade.

    Only sub-scores that are not ``None`` are considered, so this is correct
    whether one factor or all four are graded (a card with only centering simply
    returns the centering grade). The ``strategy`` (default ``OVERALL_STRATEGY``)
    selects how present sub-scores combine: ``"weighted"`` / ``"lowest"`` /
    ``"average"``. ``weights`` overrides ``OVERALL_WEIGHTS`` for the weighted
    strategy (e.g. weights learned by calibration). Rounded to the nearest 0.5.
    """
    strategy = strategy or OVERALL_STRATEGY
    weights = weights or OVERALL_WEIGHTS
    present = {name: score for name, score in sub_scores.items() if score is not None}
    if not present:
        return None
    values = list(present.values())

    if strategy == "lowest":
        raw = min(values)
    elif strategy == "average":
        raw = sum(values) / len(values)
    elif strategy == "weighted":
        w = {name: weights.get(name, 0.0) for name in present}
        total_w = sum(w.values())
        if total_w <= 0:  # no configured weights -> fall back to a plain mean
            raw = sum(values) / len(values)
        else:
            raw = sum(present[name] * w[name] for name in present) / total_w
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
    calibration=None,
) -> CardGrade:
    """Build a full :class:`CardGrade` from centering + condition wear scores.

    Any of the condition wear scores may be ``None`` (that factor not assessed),
    in which case its sub-grade stays ``None`` and is left out of the overall.

    If ``calibration`` (a ``calibration.Calibration``) is supplied, its data-fit
    curves replace the static scale lookups for whichever factors it has learned,
    and its learned weights drive the overall. Factors it hasn't learned fall
    back to the default scales, so a partially-trained calibration is fine.
    """
    # Centering.
    if calibration is not None and calibration.centering is not None:
        worse = worse_centering_percent(horizontal_ratio, vertical_ratio)
        centering_grade = calibration.centering.grade(worse)
        centering_label = label_for_grade(centering_grade, CENTERING_GRADE_SCALE)
    else:
        centering_grade, centering_label = grade_centering(horizontal_ratio, vertical_ratio)

    grade = CardGrade(
        centering_ratio_h=horizontal_ratio,
        centering_ratio_v=vertical_ratio,
        centering_grade=centering_grade,
        centering_label=centering_label,
    )

    def _factor(wear, curve, grader, scale):
        if calibration is not None and curve is not None:
            g = curve.grade(wear)
            return g, label_for_grade(g, scale)
        return grader(wear)

    cal_corners = calibration.corners if calibration is not None else None
    cal_edges = calibration.edges if calibration is not None else None
    cal_surface = calibration.surface if calibration is not None else None

    if corner_wear is not None:
        grade.corners, grade.corners_label = _factor(
            corner_wear, cal_corners, grade_corners, CORNER_GRADE_SCALE)
    if edge_wear is not None:
        grade.edges, grade.edges_label = _factor(
            edge_wear, cal_edges, grade_edges, EDGE_GRADE_SCALE)
    if surface_wear is not None:
        grade.surface, grade.surface_label = _factor(
            surface_wear, cal_surface, grade_surface, SURFACE_GRADE_SCALE)

    cal_strategy = calibration.overall_strategy if calibration is not None else None
    cal_weights = calibration.overall_weights if calibration is not None else None
    if cal_strategy or cal_weights:
        grade.overall = compute_overall(grade.sub_scores(),
                                        strategy=cal_strategy or "weighted",
                                        weights=cal_weights)
    else:
        grade.overall = compute_overall(grade.sub_scores(), strategy=overall_strategy)
    return grade


def build_grade(
    horizontal_ratio: tuple[float, float],
    vertical_ratio: tuple[float, float],
) -> CardGrade:
    """Build a centering-only :class:`CardGrade` (condition factors left as stubs)."""
    return build_full_grade(horizontal_ratio, vertical_ratio)


def build_grade_direct(
    horizontal_ratio: tuple[float, float],
    vertical_ratio: tuple[float, float],
    corners: Optional[float] = None,
    edges: Optional[float] = None,
    surface: Optional[float] = None,
    calibration=None,
) -> CardGrade:
    """Assemble a :class:`CardGrade` from DIRECT condition sub-grades (1-10).

    Used by the ML grader, which predicts corner/edge/surface grades directly
    (rather than a wear score the scale maps). Centering is still measured/
    calibrated (it's geometric and reliable). Labels come from the nearest scale
    tier; the overall honours a calibration's strategy/weights.
    """
    if calibration is not None and calibration.centering is not None:
        worse = worse_centering_percent(horizontal_ratio, vertical_ratio)
        centering_grade = calibration.centering.grade(worse)
        centering_label = label_for_grade(centering_grade, CENTERING_GRADE_SCALE)
    else:
        centering_grade, centering_label = grade_centering(horizontal_ratio, vertical_ratio)

    grade = CardGrade(
        centering_ratio_h=horizontal_ratio,
        centering_ratio_v=vertical_ratio,
        centering_grade=centering_grade,
        centering_label=centering_label,
    )
    if corners is not None:
        grade.corners, grade.corners_label = corners, label_for_grade(corners, CORNER_GRADE_SCALE)
    if edges is not None:
        grade.edges, grade.edges_label = edges, label_for_grade(edges, EDGE_GRADE_SCALE)
    if surface is not None:
        grade.surface, grade.surface_label = surface, label_for_grade(surface, SURFACE_GRADE_SCALE)

    cal_strategy = calibration.overall_strategy if calibration is not None else None
    cal_weights = calibration.overall_weights if calibration is not None else None
    if cal_strategy or cal_weights:
        grade.overall = compute_overall(grade.sub_scores(),
                                        strategy=cal_strategy or "weighted", weights=cal_weights)
    else:
        grade.overall = compute_overall(grade.sub_scores())
    return grade


def combine_grades(
    front: CardGrade,
    back: Optional[CardGrade],
    overall_strategy: Optional[str] = None,
    overall_weights: Optional[dict] = None,
) -> CardGrade:
    """Combine a card's front and back grades into one card grade.

    A defect on *either* face counts, so each sub-grade is the **worse (lower)**
    of the two sides; centering keeps the worse side's ratios. The overall is
    recomputed from the combined sub-grades. With ``back=None`` the front grade
    is returned unchanged (single-sided).
    """
    if back is None:
        return front

    # Centering: the worse side governs (and we keep that side's ratios).
    if front.centering_grade <= back.centering_grade:
        cg, cl = front.centering_grade, front.centering_label
        ch, cv = front.centering_ratio_h, front.centering_ratio_v
    else:
        cg, cl = back.centering_grade, back.centering_label
        ch, cv = back.centering_ratio_h, back.centering_ratio_v

    combined = CardGrade(
        centering_ratio_h=ch, centering_ratio_v=cv,
        centering_grade=cg, centering_label=cl,
    )

    def worst(a: Optional[float], b: Optional[float], scale):
        vals = [v for v in (a, b) if v is not None]
        if not vals:
            return None, ""
        g = min(vals)
        return g, label_for_grade(g, scale)

    combined.corners, combined.corners_label = worst(front.corners, back.corners, CORNER_GRADE_SCALE)
    combined.edges, combined.edges_label = worst(front.edges, back.edges, EDGE_GRADE_SCALE)
    combined.surface, combined.surface_label = worst(front.surface, back.surface, SURFACE_GRADE_SCALE)

    if overall_strategy or overall_weights:
        combined.overall = compute_overall(combined.sub_scores(),
                                           strategy=overall_strategy or "weighted",
                                           weights=overall_weights)
    else:
        combined.overall = compute_overall(combined.sub_scores())
    return combined
