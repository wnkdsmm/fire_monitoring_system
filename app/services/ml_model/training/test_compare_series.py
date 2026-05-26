from __future__ import annotations

from app.services.ml_model.training.compare_series import build_compare_series


def test_compare_series_both_years_fact() -> None:
    daily = [
        {"date": "2024-05-01", "count": 3},
        {"date": "2024-05-02", "count": 4},
        {"date": "2025-05-01", "count": 5},
        {"date": "2025-05-02", "count": 6},
    ]
    result = build_compare_series(
        month=5,
        year_a=2025,
        year_b=2024,
        daily_history=daily,
        ml_month_provider=lambda _y, _m: {},
    )
    assert result["rows"][0]["a_source"] == "fact"
    assert result["rows"][0]["b_source"] == "fact"
    assert result["a_summary"]["fact_days"] >= 2
    assert result["b_summary"]["fact_days"] >= 2


def test_compare_series_year_b_from_ml_when_no_facts() -> None:
    daily = [{"date": "2025-05-01", "count": 5}]

    def _provider(year: int, _month: int) -> dict[int, float | None]:
        return {1: 7.0} if year == 2024 else {}

    result = build_compare_series(
        month=5,
        year_a=2025,
        year_b=2024,
        daily_history=daily,
        ml_month_provider=_provider,
    )
    first = result["rows"][0]
    assert first["a_source"] == "fact"
    assert first["b_source"] == "ml"
    assert first["b_value"] == 7.0


def test_compare_series_both_ml_when_no_facts() -> None:
    def _provider(year: int, _month: int) -> dict[int, float | None]:
        return {1: float(year)}

    result = build_compare_series(
        month=5,
        year_a=2025,
        year_b=2024,
        daily_history=[],
        ml_month_provider=_provider,
    )
    first = result["rows"][0]
    assert first["a_source"] == "ml"
    assert first["b_source"] == "ml"
    assert first["a_value"] == 2025.0
    assert first["b_value"] == 2024.0


def test_compare_series_partial_fact_hybrid_legacy_mode() -> None:
    """Legacy behaviour (treat_missing_as_zero=False): a covered month with
    only one fact-day still imputes ML for the rest."""
    daily = [{"date": "2025-05-01", "count": 9}]

    def _provider(year: int, _month: int) -> dict[int, float | None]:
        return {1: 1.0, 2: 2.0} if year == 2025 else {1: 3.0, 2: 4.0}

    result = build_compare_series(
        month=5,
        year_a=2025,
        year_b=2024,
        daily_history=daily,
        ml_month_provider=_provider,
        treat_missing_as_zero=False,
    )
    assert result["rows"][0]["a_source"] == "fact"
    assert result["rows"][1]["a_source"] == "ml"
    assert result["a_summary"]["fact_days"] == 1
    assert result["a_summary"]["ml_days"] >= 1


def test_compare_series_covered_month_treats_missing_days_as_zero() -> None:
    """New default behaviour: inside the observed window [min_date, max_date],
    days without a record are real zeros (not ML imputations). Days outside
    that window stay on ML — see the cut-off tests below."""
    # Two fact-days framing the whole of May 2025 → entire month is inside
    # [2025-05-01, 2025-05-31] window.
    daily = [
        {"date": "2025-05-01", "count": 9},
        {"date": "2025-05-31", "count": 4},
    ]

    def _provider(year: int, _month: int) -> dict[int, float | None]:
        return {1: 1.0, 2: 2.0}

    result = build_compare_series(
        month=5,
        year_a=2025,
        year_b=2024,
        daily_history=daily,
        ml_month_provider=_provider,
    )
    # Day 1: real fact (9)
    assert result["rows"][0]["a_source"] == "fact"
    assert result["rows"][0]["a_value"] == 9.0
    # Day 2 of May 2025: no record but May 2025 covered AND inside window → true zero
    assert result["rows"][1]["a_source"] == "fact"
    assert result["rows"][1]["a_value"] == 0.0
    # Day 3: same logic → true zero
    assert result["rows"][2]["a_source"] == "fact"
    assert result["rows"][2]["a_value"] == 0.0
    # Day 31: real fact again
    assert result["rows"][30]["a_source"] == "fact"
    assert result["rows"][30]["a_value"] == 4.0
    # Year_b 2024 has no data at all → uncovered → still uses ML
    assert result["rows"][0]["b_source"] == "ml"
    assert result["rows"][0]["b_value"] == 1.0


def test_compare_series_data_cuts_off_mid_month_uses_ml_for_tail() -> None:
    """If data ends on day 10 of the target month, days 11..end must NOT be
    treated as true zeros — they fall outside the observed window and stay
    on the OLS baseline."""
    # Data goes only up to 2025-05-10 (table dumped mid-month).
    daily = [
        {"date": "2025-05-01", "count": 2},
        {"date": "2025-05-05", "count": 4},
        {"date": "2025-05-10", "count": 3},
    ]

    def _provider(_year: int, _month: int) -> dict[int, float | None]:
        return {day: float(day) for day in range(1, 32)}

    result = build_compare_series(
        month=5,
        year_a=2025,
        year_b=2024,
        daily_history=daily,
        ml_month_provider=_provider,
    )
    rows = result["rows"]
    # Day 1 — explicit fact.
    assert rows[0]["a_source"] == "fact"
    assert rows[0]["a_value"] == 2.0
    # Day 2, 3, 4 — inside [min, max] window, month covered, no record → true zero.
    assert rows[1]["a_source"] == "fact" and rows[1]["a_value"] == 0.0
    assert rows[2]["a_source"] == "fact" and rows[2]["a_value"] == 0.0
    assert rows[3]["a_source"] == "fact" and rows[3]["a_value"] == 0.0
    # Day 10 — explicit fact again.
    assert rows[9]["a_source"] == "fact"
    assert rows[9]["a_value"] == 3.0
    # Day 11..31 — past max_observed_date (2025-05-10) → must be ML.
    assert rows[10]["a_source"] == "ml"
    assert rows[10]["a_value"] == 11.0
    assert rows[30]["a_source"] == "ml"
    assert rows[30]["a_value"] == 31.0


def test_compare_series_data_starts_mid_month_uses_ml_for_head() -> None:
    """Symmetric case: data starts on day 20 of the target month. Days 1..19
    must stay on OLS, not be silently zeroed."""
    daily = [
        {"date": "2025-05-20", "count": 5},
        {"date": "2025-05-25", "count": 7},
    ]

    def _provider(_year: int, _month: int) -> dict[int, float | None]:
        return {day: 100.0 + day for day in range(1, 32)}

    result = build_compare_series(
        month=5,
        year_a=2025,
        year_b=2024,
        daily_history=daily,
        ml_month_provider=_provider,
    )
    rows = result["rows"]
    # Day 1..19 — before min_observed_date (2025-05-20) → ML.
    assert rows[0]["a_source"] == "ml"
    assert rows[0]["a_value"] == 101.0
    assert rows[18]["a_source"] == "ml"
    # Day 20 — explicit fact.
    assert rows[19]["a_source"] == "fact"
    assert rows[19]["a_value"] == 5.0
    # Day 21..24 — inside [20, 25] window, no record → true zero.
    assert rows[20]["a_source"] == "fact" and rows[20]["a_value"] == 0.0
    assert rows[23]["a_source"] == "fact" and rows[23]["a_value"] == 0.0
    # Day 25 — explicit fact.
    assert rows[24]["a_source"] == "fact" and rows[24]["a_value"] == 7.0
    # Day 26..31 — past max_observed_date → ML again.
    assert rows[25]["a_source"] == "ml"


def test_compare_series_uncovered_month_falls_back_to_ml() -> None:
    """If the target month has no facts at all, missing days must come from
    ML — we cannot assume the table covers that month."""
    daily = [{"date": "2025-04-15", "count": 4}]  # April covered, May not

    def _provider(year: int, _month: int) -> dict[int, float | None]:
        return {1: 7.0, 2: 8.0}

    result = build_compare_series(
        month=5,
        year_a=2025,
        year_b=2024,
        daily_history=daily,
        ml_month_provider=_provider,
    )
    # May 2025 has no facts in daily_history → uncovered → ML
    assert result["rows"][0]["a_source"] == "ml"
    assert result["rows"][0]["a_value"] == 7.0


def test_compare_series_uses_real_month_length_for_selected_years() -> None:
    result = build_compare_series(
        month=2,
        year_a=2024,
        year_b=2023,
        daily_history=[],
        ml_month_provider=lambda _y, _m: {},
    )
    assert len(result["rows"]) == 29
    assert result["rows"][-1]["day"] == 29
