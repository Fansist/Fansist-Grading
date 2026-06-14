"""Tests for grading.py: the centering scale, overall combination, CardGrade."""

import pytest

from grading import (
    CardGrade,
    build_grade,
    compute_overall,
    grade_centering,
    worse_centering_percent,
)


def test_worse_percent_picks_largest_side_across_axes():
    assert worse_centering_percent((58.0, 42.0), (52.0, 48.0)) == 58.0
    assert worse_centering_percent((50.0, 50.0), (50.0, 50.0)) == 50.0


@pytest.mark.parametrize(
    "h_ratio, v_ratio, expected_grade, expected_label",
    [
        ((50.0, 50.0), (50.0, 50.0), 10.0, "Gem Mint"),
        ((55.0, 45.0), (50.0, 50.0), 10.0, "Gem Mint"),   # boundary: 55 -> still 10
        ((60.0, 40.0), (50.0, 50.0), 9.0, "Mint"),         # boundary: 60 -> 9
        ((62.0, 38.0), (50.0, 50.0), 8.0, "NM-MT"),
        ((70.0, 30.0), (50.0, 50.0), 7.0, "Near Mint"),    # boundary: 70 -> 7
        ((95.0, 5.0), (50.0, 50.0), 1.0, "Poor"),
    ],
)
def test_grade_centering_scale(h_ratio, v_ratio, expected_grade, expected_label):
    grade, label = grade_centering(h_ratio, v_ratio)
    assert grade == expected_grade
    assert label == expected_label


def test_worse_axis_drives_the_grade():
    # Horizontal perfect, vertical bad -> graded on the bad (vertical) axis.
    # worse = 64 falls in the <=65 bucket (grade 8); a 50/50 horizontal alone
    # would have scored 10, so this proves the worse axis governs.
    grade, _ = grade_centering((50.0, 50.0), (64.0, 36.0))
    assert grade == 8.0


def test_compute_overall_centering_only_equals_centering():
    scores = {"centering": 9.0, "corners": None, "edges": None, "surface": None}
    assert compute_overall(scores) == 9.0


def test_compute_overall_averages_present_subscores():
    scores = {"centering": 9.0, "corners": 7.0, "edges": None, "surface": 8.0}
    # (9 + 7 + 8) / 3 = 8.0
    assert compute_overall(scores) == 8.0


def test_compute_overall_all_none_is_none():
    assert compute_overall({"centering": None, "corners": None}) is None


def test_build_grade_fills_centering_and_stubs():
    grade = build_grade((40.0, 60.0), (50.0, 50.0))
    assert isinstance(grade, CardGrade)
    assert grade.centering_grade == 9.0          # worse = 60 -> Mint
    assert grade.centering_label == "Mint"
    assert grade.corners is None
    assert grade.edges is None
    assert grade.surface is None
    # v1: overall is driven purely by centering.
    assert grade.overall == grade.centering_grade


def test_to_dict_has_expected_keys():
    grade = build_grade((40.0, 60.0), (50.0, 50.0))
    d = grade.to_dict()
    assert set(d) == {
        "centering_ratio_h", "centering_ratio_v", "centering_grade",
        "centering_label", "corners", "edges", "surface", "overall",
    }
    assert d["centering_ratio_h"] == [40.0, 60.0]
