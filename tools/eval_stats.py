"""Run-to-run spread and the comparison of two settings (D-062; qa-eval-harness step 6).

Every headline measure is a ratio of sums over items (accuracy is correct/1 per item, recall is
caught/wanted per item), so a measure is held as a *vector*: `{item_id: (numerator, denominator)}`.
That one shape feeds both tests:

- **Spread between passes.** The measure is computed once per pass; the passes give a mean, a
  standard deviation and a 95% t-interval. For two settings the interval is on the difference of
  their means (Welch).
- **Paired bootstrap over items.** The same items are resampled for both settings, so an item that
  is hard for both cancels out. The interval is on the difference of the two settings' measures.

A difference is called real only if it is bigger than the pass interval **and** the bootstrap
interval excludes zero. Meeting one is "unclear", not "no effect". Pure functions, no model.
"""

import math
import random
import statistics
from collections.abc import Sequence
from typing import Any

Vector = dict[str, tuple[float, float]]  # item id -> (numerator, denominator)

T_95 = (
    12.706,
    4.303,
    3.182,
    2.776,
    2.571,
    2.447,
    2.365,
    2.306,
    2.262,
    2.228,
    2.201,
    2.179,
    2.160,
    2.145,
    2.131,
    2.120,
    2.110,
    2.101,
    2.093,
    2.086,
    2.080,
    2.074,
    2.069,
    2.064,
    2.060,
    2.056,
    2.052,
    2.048,
    2.045,
    2.042,
)  # two-sided 95% critical values of Student's t for 1 to 30 degrees of freedom
BEYOND_TABLE = 2.0  # slightly above the large-sample 1.96, so the interval errs on the wide side


def t_critical(df: int) -> float:
    if df < 1:
        raise ValueError("a t-interval needs at least one degree of freedom")
    return T_95[df - 1] if df <= len(T_95) else BEYOND_TABLE


# --- spread between passes ---------------------------------------------------------------------


def spread(values: Sequence[float | None]) -> dict[str, Any]:
    """Mean, sample standard deviation, range and the 95% t-interval half-width of the mean."""
    present = [v for v in values if v is not None]
    if not present:
        return {
            "n": 0,
            "mean": None,
            "sd": None,
            "min": None,
            "max": None,
            "half_width_95": None,
        }
    sd = statistics.stdev(present) if len(present) > 1 else None
    return {
        "n": len(present),
        "mean": statistics.fmean(present),
        "sd": sd,
        "min": min(present),
        "max": max(present),
        "half_width_95": None
        if sd is None
        else t_critical(len(present) - 1) * sd / math.sqrt(len(present)),
    }


def difference_half_width(
    a: Sequence[float | None], b: Sequence[float | None]
) -> tuple[float, int] | None:
    """Half-width of the 95% interval on mean(a) - mean(b) from the spread between passes (Welch).

    None when either setting has fewer than two passes: the spread cannot be estimated.
    """
    xs = [v for v in a if v is not None]
    ys = [v for v in b if v is not None]
    if len(xs) < 2 or len(ys) < 2:
        return None
    va, vb = statistics.variance(xs) / len(xs), statistics.variance(ys) / len(ys)
    if va + vb == 0:
        return 0.0, len(xs) + len(ys) - 2
    df = (va + vb) ** 2 / (va**2 / (len(xs) - 1) + vb**2 / (len(ys) - 1))
    return t_critical(max(1, math.floor(df))) * math.sqrt(va + vb), max(1, math.floor(df))


# --- measures over items -----------------------------------------------------------------------


def measure_value(vector: Vector) -> float | None:
    numerator = sum(n for n, _ in vector.values())
    denominator = sum(d for _, d in vector.values())
    return None if denominator == 0 else numerator / denominator


def average_vectors(vectors: Sequence[Vector]) -> Vector:
    """One vector from several passes: each item's numerator and denominator averaged."""
    if not vectors:
        raise ValueError("no passes to average")
    ids = set(vectors[0])
    if any(set(v) != ids for v in vectors):
        raise ValueError("the passes do not cover the same items")
    return {
        item: (
            statistics.fmean(v[item][0] for v in vectors),
            statistics.fmean(v[item][1] for v in vectors),
        )
        for item in sorted(ids)
    }


def paired_bootstrap(
    a: Vector, b: Vector, *, resamples: int = 10_000, seed: int = 0
) -> dict[str, Any]:
    """Resample the items both settings have, together, and give a 95% interval on a - b."""
    ids = sorted(set(a) & set(b))
    nothing: dict[str, Any] = {
        "n_items": len(ids),
        "diff": None,
        "ci_low": None,
        "ci_high": None,
        "resamples": 0,
        "skipped": 0,
    }
    a_cells = [a[i] for i in ids]
    b_cells = [b[i] for i in ids]
    point_a = measure_value({i: a[i] for i in ids})
    point_b = measure_value({i: b[i] for i in ids})
    if point_a is None or point_b is None:
        return nothing
    rng = random.Random(seed)  # noqa: S311 (a seeded sample, not a secret)
    diffs: list[float] = []
    skipped = 0
    count = len(ids)
    for _ in range(resamples):
        picks = [rng.randrange(count) for _ in range(count)]
        den_a = sum(a_cells[p][1] for p in picks)
        den_b = sum(b_cells[p][1] for p in picks)
        if den_a == 0 or den_b == 0:
            skipped += 1
            continue
        diffs.append(
            sum(a_cells[p][0] for p in picks) / den_a - sum(b_cells[p][0] for p in picks) / den_b
        )
    if not diffs:
        return nothing | {"skipped": skipped}
    diffs.sort()
    low = diffs[int(0.025 * (len(diffs) - 1))]
    high = diffs[math.ceil(0.975 * (len(diffs) - 1))]
    return {
        "n_items": len(ids),
        "diff": point_a - point_b,
        "ci_low": low,
        "ci_high": high,
        "resamples": len(diffs),
        "skipped": skipped,
    }


def excludes_zero(low: float | None, high: float | None) -> bool:
    return low is not None and high is not None and (low > 0 or high < 0)


def verdict(
    diff: float | None, half_width: float | None, ci_low: float | None, ci_high: float | None
) -> dict[str, Any]:
    """ "real" only if the difference beats the pass interval and the bootstrap excludes zero."""
    if diff is None or ci_low is None or ci_high is None:
        return {
            "call": "unclear",
            "why": "there were no items to compare",
            "higher": None,
            "smallest_detectable": None,
            "note": None,
        }
    boot_ok = excludes_zero(ci_low, ci_high)
    smallest = max(half_width or 0.0, (ci_high - ci_low) / 2)
    note = (
        "the passes had no spread between them, so only the bootstrap decides"
        if half_width == 0
        else None
    )
    if half_width is None:
        return {
            "call": "unclear",
            "why": "the spread between passes cannot be estimated: it needs at least two passes "
            "of each setting",
            "higher": None,
            "smallest_detectable": smallest,
            "note": note,
        }
    beats_spread = abs(diff) > half_width
    if beats_spread and boot_ok:
        return {
            "call": "real",
            "why": "the difference is larger than the pass-to-pass interval and the paired "
            "bootstrap excludes zero",
            "higher": "a" if diff > 0 else "b",
            "smallest_detectable": smallest,
            "note": note,
        }
    failed = []
    if not beats_spread:
        failed.append("the difference is within the pass spread")
    if not boot_ok:
        failed.append("the paired bootstrap includes zero")
    return {
        "call": "unclear",
        "why": " and ".join(failed),
        "higher": None,
        "smallest_detectable": smallest,
        "note": note,
    }


# --- whole comparisons -------------------------------------------------------------------------

Pass = dict[str, Vector]  # measure name -> vector, for one pass


def spread_of_passes(passes: Sequence[Pass]) -> dict[str, Any]:
    """For one setting: each measure per pass, its spread, and the items whose result moved."""
    out: dict[str, Any] = {}
    for name in sorted(set.intersection(*(set(p) for p in passes))):
        values = [measure_value(p[name]) for p in passes]
        ids = sorted(set.intersection(*(set(p[name]) for p in passes)))
        moved = [i for i in ids if len({p[name][i] for p in passes}) > 1]
        out[name] = {"values": values, "spread": spread(values), "items_that_moved": moved}
    return out


def compare(
    passes_a: Sequence[Pass],
    passes_b: Sequence[Pass],
    *,
    resamples: int = 10_000,
    seed: int = 0,
) -> dict[str, Any]:
    """Compare two settings measure by measure. `a - b` throughout."""
    out: dict[str, Any] = {}
    names = set.intersection(*(set(p) for p in [*passes_a, *passes_b]))
    for name in sorted(names):
        values_a = [measure_value(p[name]) for p in passes_a]
        values_b = [measure_value(p[name]) for p in passes_b]
        boot = paired_bootstrap(
            average_vectors([p[name] for p in passes_a]),
            average_vectors([p[name] for p in passes_b]),
            resamples=resamples,
            seed=seed,
        )
        mean_a, mean_b = spread(values_a)["mean"], spread(values_b)["mean"]
        diff = None if mean_a is None or mean_b is None else mean_a - mean_b
        interval = difference_half_width(values_a, values_b)
        out[name] = {
            "a": spread(values_a),
            "b": spread(values_b),
            "diff": diff,
            "pass_interval_half_width": None if interval is None else interval[0],
            "pass_interval_df": None if interval is None else interval[1],
            "bootstrap": boot,
            "verdict": verdict(
                diff,
                None if interval is None else interval[0],
                boot["ci_low"],
                boot["ci_high"],
            ),
        }
    return out
