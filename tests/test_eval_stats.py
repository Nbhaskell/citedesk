"""The spread test: t-intervals between passes and a paired bootstrap over items (D-062)."""

import math

import pytest

from tools import eval_stats as st

# --- the t table and the spread of a few numbers -----------------------------------------------


@pytest.mark.parametrize(("df", "expected"), [(1, 12.706), (2, 4.303), (4, 2.776), (30, 2.042)])
def test_the_t_value_is_the_two_sided_95_percent_one(df: int, expected: float) -> None:
    assert st.t_critical(df) == expected


def test_beyond_the_table_the_value_stays_on_the_safe_side() -> None:
    assert st.t_critical(31) >= 1.96
    assert st.t_critical(500) >= 1.96


def test_no_degrees_of_freedom_gives_no_interval() -> None:
    with pytest.raises(ValueError, match="at least one"):
        st.t_critical(0)


def test_spread_of_three_passes() -> None:
    result = st.spread([0.80, 0.82, 0.84])
    assert result["n"] == 3
    assert result["mean"] == pytest.approx(0.82)
    assert result["sd"] == pytest.approx(0.02)
    assert (result["min"], result["max"]) == (0.80, 0.84)
    assert result["half_width_95"] == pytest.approx(4.303 * 0.02 / math.sqrt(3))


def test_one_pass_has_no_spread() -> None:
    result = st.spread([0.8])
    assert result["sd"] is None and result["half_width_95"] is None
    assert result["mean"] == 0.8


def test_passes_that_agree_have_a_zero_wide_interval() -> None:
    assert st.spread([0.5, 0.5, 0.5])["half_width_95"] == 0.0


def test_missing_values_are_left_out_of_the_spread() -> None:
    assert st.spread([0.5, None, 0.7])["n"] == 2
    assert st.spread([None, None])["mean"] is None


# --- the interval on a difference between two settings -----------------------------------------


def test_the_difference_interval_comes_from_both_spreads() -> None:
    half, df = st.difference_half_width([0.80, 0.82, 0.84], [0.70, 0.72, 0.74]) or (None, None)
    assert df == 4  # equal spreads, three passes each
    assert half == pytest.approx(st.t_critical(4) * math.sqrt(0.02**2 / 3 * 2))


def test_the_difference_interval_needs_two_passes_each() -> None:
    assert st.difference_half_width([0.8], [0.7, 0.72]) is None
    assert st.difference_half_width([0.8, 0.8], [0.7]) is None


def test_passes_with_no_spread_give_a_zero_interval() -> None:
    assert st.difference_half_width([0.8, 0.8], [0.7, 0.7]) == (0.0, 2)


# --- measures made of per-item numerators and denominators -------------------------------------


def test_a_measure_is_the_sum_of_numerators_over_the_sum_of_denominators() -> None:
    vector = {"a": (1.0, 1.0), "b": (0.0, 1.0), "c": (1.0, 1.0), "d": (0.0, 0.0)}
    assert st.measure_value(vector) == pytest.approx(2 / 3)
    assert st.measure_value({"a": (0.0, 0.0)}) is None


def test_averaging_passes_averages_each_item() -> None:
    first = {"a": (1.0, 1.0), "b": (0.0, 1.0)}
    second = {"a": (0.0, 1.0), "b": (0.0, 1.0)}
    assert st.average_vectors([first, second]) == {"a": (0.5, 1.0), "b": (0.0, 1.0)}


def test_passes_must_cover_the_same_items() -> None:
    with pytest.raises(ValueError, match="same items"):
        st.average_vectors([{"a": (1.0, 1.0)}, {"b": (1.0, 1.0)}])


def vector(*correct: int) -> dict[str, tuple[float, float]]:
    return {f"i{n}": (float(c), 1.0) for n, c in enumerate(correct)}


# --- the paired bootstrap ----------------------------------------------------------------------


def test_the_bootstrap_is_repeatable_with_a_seed() -> None:
    a, b = vector(*([1] * 40 + [0] * 10)), vector(*([1] * 30 + [0] * 20))
    assert st.paired_bootstrap(a, b, resamples=500, seed=3) == st.paired_bootstrap(
        a, b, resamples=500, seed=3
    )


def test_identical_systems_have_a_zero_difference_and_an_interval_on_zero() -> None:
    a = vector(*([1] * 40 + [0] * 10))
    result = st.paired_bootstrap(a, dict(a), resamples=300)
    assert result["diff"] == 0.0
    assert result["ci_low"] == 0.0 and result["ci_high"] == 0.0
    assert not st.excludes_zero(result["ci_low"], result["ci_high"])


def test_a_clear_gain_on_many_items_excludes_zero() -> None:
    better = vector(*([1] * 90 + [0] * 10))
    worse = vector(*([1] * 20 + [0] * 80))
    result = st.paired_bootstrap(better, worse, resamples=1000)
    assert result["diff"] == pytest.approx(0.70)
    assert st.excludes_zero(result["ci_low"], result["ci_high"])


def test_pairing_matters_more_than_the_totals() -> None:
    """Same totals, but the systems fail on different items: the paired interval is wide."""
    a = vector(*([1] * 5 + [0] * 5))
    b = vector(*([0] * 5 + [1] * 5))
    result = st.paired_bootstrap(a, b, resamples=1000)
    assert result["diff"] == 0.0
    assert result["ci_low"] < 0 < result["ci_high"]


def test_only_items_both_systems_have_are_paired() -> None:
    a = {"x": (1.0, 1.0), "y": (1.0, 1.0), "only_a": (1.0, 1.0)}
    b = {"x": (0.0, 1.0), "y": (0.0, 1.0), "only_b": (0.0, 1.0)}
    result = st.paired_bootstrap(a, b, resamples=50)
    assert result["n_items"] == 2 and result["diff"] == 1.0


def test_nothing_to_pair_gives_no_interval() -> None:
    result = st.paired_bootstrap({"x": (1.0, 0.0)}, {"x": (1.0, 0.0)}, resamples=20)
    assert result["diff"] is None and result["ci_low"] is None


# --- the verdict: both conditions, or "unclear" ------------------------------------------------


def test_a_difference_is_real_only_when_both_tests_agree() -> None:
    assert st.verdict(0.10, 0.03, 0.04, 0.16)["call"] == "real"


def test_passing_only_the_bootstrap_is_unclear() -> None:
    result = st.verdict(0.10, 0.20, 0.04, 0.16)
    assert result["call"] == "unclear"
    assert "pass spread" in result["why"]


def test_passing_only_the_pass_interval_is_unclear() -> None:
    result = st.verdict(0.10, 0.03, -0.05, 0.25)
    assert result["call"] == "unclear"
    assert "bootstrap" in result["why"]


def test_one_pass_each_cannot_be_called() -> None:
    result = st.verdict(0.10, None, 0.04, 0.16)
    assert result["call"] == "unclear"
    assert "two passes" in result["why"]


def test_an_unclear_call_says_how_big_a_difference_the_test_could_see() -> None:
    result = st.verdict(0.01, 0.03, -0.05, 0.07)
    assert result["smallest_detectable"] == pytest.approx(0.06)


def test_a_direction_is_given_for_a_real_difference() -> None:
    assert st.verdict(-0.10, 0.03, -0.16, -0.04)["higher"] == "b"
    assert st.verdict(0.10, 0.03, 0.04, 0.16)["higher"] == "a"
    assert st.verdict(0.0, 0.03, -0.01, 0.01)["higher"] is None


def test_passes_that_never_differ_leave_the_decision_to_the_bootstrap() -> None:
    result = st.verdict(0.10, 0.0, 0.04, 0.16)
    assert result["call"] == "real"
    assert "no spread" in result["note"]


# --- comparing two settings over several passes ------------------------------------------------


def pass_of(correct: int, total: int = 50) -> dict[str, dict[str, tuple[float, float]]]:
    return {"accuracy": vector(*([1] * correct + [0] * (total - correct)))}


def test_comparing_two_settings_gives_a_call_per_measure() -> None:
    a = [pass_of(45), pass_of(44), pass_of(45)]
    b = [pass_of(20), pass_of(21), pass_of(20)]
    result = st.compare(a, b, resamples=500)
    row = result["accuracy"]
    assert row["a"]["mean"] > row["b"]["mean"]
    assert row["verdict"]["call"] == "real"
    assert row["verdict"]["higher"] == "a"


def test_comparing_noisy_passes_of_similar_settings_is_unclear() -> None:
    a = [pass_of(30), pass_of(40), pass_of(35)]
    b = [pass_of(36), pass_of(31), pass_of(38)]
    row = st.compare(a, b, resamples=500)["accuracy"]
    assert row["verdict"]["call"] == "unclear"


def test_the_spread_of_one_setting_names_items_that_moved() -> None:
    passes = [
        {"accuracy": {"a": (1.0, 1.0), "b": (1.0, 1.0), "c": (0.0, 1.0)}},
        {"accuracy": {"a": (1.0, 1.0), "b": (0.0, 1.0), "c": (0.0, 1.0)}},
        {"accuracy": {"a": (1.0, 1.0), "b": (1.0, 1.0), "c": (0.0, 1.0)}},
    ]
    row = st.spread_of_passes(passes)["accuracy"]
    assert row["values"] == [pytest.approx(2 / 3), pytest.approx(1 / 3), pytest.approx(2 / 3)]
    assert row["items_that_moved"] == ["b"]
    assert row["spread"]["n"] == 3
