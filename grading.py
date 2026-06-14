"""grading.py

Map centering ratios to a centering sub-grade and assemble a card grade.

v1 grades CENTERING ONLY. The :class:`CardGrade` dataclass already carries
stubbed ``corners`` / ``edges`` / ``surface`` fields (default ``None``) and an
``overall`` that is computed from whatever sub-scores are present. When those
other graders are added later, they drop straight into the same structure and
:func:`compute_overall` starts including them -- no rewrite of the core needed.

The centering scale below is intentionally a plain, easy-to-edit table of
thresholds (loosely modelled on hobby grading tolerances). Tune the numbers to
match the grading standard you care about.
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


@dataclass
class CardGrade:
    """A card grade. v1 fills only the centering fields; the rest are stubs.

    Attributes:
        centering_ratio_h: (left%, right%) horizontal centering, summing to 100.
        centering_ratio_v: (top%, bottom%) vertical centering, summing to 100.
        centering_grade: Numeric centering sub-grade (e.g. 1-10).
        centering_label: Human-readable label for the centering sub-grade.
        corners / edges / surface: Future sub-grades, ``None`` until implemented.
        overall: Combined grade computed from the available sub-scores.
    """

    centering_ratio_h: tuple[float, float]
    centering_ratio_v: tuple[float, float]
    centering_grade: float
    centering_label: str = ""

    # --- Stubs for future grading dimensions (kept None in v1) ---------------
    corners: Optional[float] = None
    edges: Optional[float] = None
    surface: Optional[float] = None

    overall: Optional[float] = field(default=None)

    def sub_scores(self) -> dict[str, Optional[float]]:
        """All sub-scores by name, including the not-yet-implemented stubs."""
        return {
            "centering": self.centering_grade,
            "corners": self.corners,
            "edges": self.edges,
            "surface": self.surface,
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


def compute_overall(sub_scores: dict[str, Optional[float]]) -> Optional[float]:
    """Combine the available sub-scores into an overall grade.

    v1 has only centering, so the overall simply equals it. The implementation
    averages every sub-score that is present (ignoring ``None`` stubs), so when
    corners/edges/surface are added later they are included automatically with
    no change here. Swap the averaging for a "lowest sub-grade wins" or weighted
    rule if your grading standard requires it.
    """
    present = [score for score in sub_scores.values() if score is not None]
    if not present:
        return None
    return round(sum(present) / len(present), 1)


def build_grade(
    horizontal_ratio: tuple[float, float],
    vertical_ratio: tuple[float, float],
) -> CardGrade:
    """Build a :class:`CardGrade` from centering ratios (v1 entry point)."""
    centering_grade, centering_label = grade_centering(horizontal_ratio, vertical_ratio)

    grade = CardGrade(
        centering_ratio_h=horizontal_ratio,
        centering_ratio_v=vertical_ratio,
        centering_grade=centering_grade,
        centering_label=centering_label,
    )
    grade.overall = compute_overall(grade.sub_scores())
    return grade
