from deaths_warrant.years_lost import integrate_step, summarise_years; import pytest
from deaths_warrant.aj import aalen_johansen
from deaths_warrant.km import kaplan_meier
from lifelines import KaplanMeierFitter; from lifelines.utils import restricted_mean_survival_time

# Check the area under a hand-calculated survival step curve.
def test_integrate_step_survival():
    area = integrate_step([1, 2, 3, 4], [0.8, 0.6, 0.3, 0.3], 0, 4, 1)
    assert area == pytest.approx(2.7)

# Ensure integration clips the final step at a fractional endpoint.
def test_integrate_step_partial_final_interval():
    area = integrate_step([1, 2, 3, 4], [0.8, 0.6, 0.3, 0.3], 0, 2.5, 1)
    assert area == pytest.approx(2.1)

# Ensure integration starts at the current step value inside an interval.
def test_integrate_step_start_inside_interval():
    area = integrate_step([1, 2, 3, 4], [0.8, 0.6, 0.3, 0.3], 1.5, 3.5, 1)
    assert area == pytest.approx(1.15)

# Ensure the initial curve value applies before the first recorded update.
def test_integrate_step_before_first_update():
    area = integrate_step([1, 2, 3, 4], [0.8, 0.6, 0.3, 0.3], 0, 0.5, 1)
    assert area == pytest.approx(0.5)

# Check survival and cause-incidence areas add up to the analysis window.
def test_years_lost_by_cause():
    table = aalen_johansen([1, 2, 2, 3, 4], [1, 2, 0, 1, 0])
    curve_times = table["time"].tolist()
    survival_values = table["survival"].tolist()
    years_lived = integrate_step(curve_times, survival_values, 0, 4, 1)
    cause_1 = table["cif_1"].tolist()
    years_lost_1 = integrate_step(curve_times, cause_1, 0, 4, 0)
    cause_2 = table["cif_2"].tolist()
    years_lost_2 = integrate_step(curve_times, cause_2, 0, 4, 0)
    years_summed = years_lived + years_lost_1 + years_lost_2
    assert years_lived == pytest.approx(2.7)
    assert years_lost_1 == pytest.approx(0.9)
    assert years_lost_2 == pytest.approx(0.4)
    assert years_summed == pytest.approx(4.0)

# Compare integrated survival with lifelines' restricted mean survival time.
def test_integrate_step_matches_lifelines():
    table = kaplan_meier([1, 2, 2, 3, 4], [1, 1, 0, 1, 0])
    curve_times = table["time"].tolist()
    survival_values = table["survival"].tolist()
    area = integrate_step(curve_times, survival_values, 0, 4, 1)
    reference = KaplanMeierFitter().fit([1, 2, 2, 3, 4], event_observed = [1, 1, 0, 1, 0])
    expected = restricted_mean_survival_time(reference, t=4)
    assert area == pytest.approx(expected)

# Check unconditional years lived and cause losses partition the full window.
def test_summarise_years_from_zero():
    table = aalen_johansen([1, 2, 2, 3, 4], [1, 2, 0, 1, 0])
    summary = summarise_years(table, 0, 4)
    summed_years = summary["years_lived"] + summary["years_lost_by_cause"]["cif_1"] + summary["years_lost_by_cause"]["cif_2"]
    summed_window = summary["tau"] - summary["start"]
    assert summary["start"] == 0
    assert summary["tau"] == 4
    assert summary["years_lived"] == pytest.approx(2.7)
    assert summary["years_lost_by_cause"]["cif_1"] == pytest.approx(0.9)
    assert summary["years_lost_by_cause"]["cif_2"] == pytest.approx(0.4)
    assert summed_years == pytest.approx(summed_window)

# Check years are conditioned on survival when the window starts at an event time.
def test_summarise_years_at_update():
    table = aalen_johansen([1, 2, 2, 3, 4], [1, 2, 0, 1, 0])
    summary = summarise_years(table, 2, 4)
    summed_years = summary["years_lived"] + summary["years_lost_by_cause"]["cif_1"] + summary["years_lost_by_cause"]["cif_2"]
    summed_window = summary["tau"] - summary["start"]
    assert summary["start"] == 2
    assert summary["tau"] == 4
    assert summary["years_lived"] == pytest.approx(1.5)
    assert summary["years_lost_by_cause"]["cif_1"] == pytest.approx(0.5)
    assert summary["years_lost_by_cause"]["cif_2"] == pytest.approx(0.0)
    assert summed_years == pytest.approx(summed_window)

# Check conditional year totals for a window beginning between event times.
def test_summarise_years_between_updates():
    table = aalen_johansen([1, 2, 2, 3, 4], [1, 2, 0, 1, 0])
    summary = summarise_years(table, 1.5, 3.5)
    summed_years = summary["years_lived"] + summary["years_lost_by_cause"]["cif_1"] + summary["years_lost_by_cause"]["cif_2"]
    summed_window = summary["tau"] - summary["start"]
    assert summary["start"] == 1.5
    assert summary["tau"] == 3.5
    assert summary["years_lived"] == pytest.approx(1.4375)
    assert summary["years_lost_by_cause"]["cif_1"] == pytest.approx(0.1875)
    assert summary["years_lost_by_cause"]["cif_2"] == pytest.approx(0.375)
    assert summed_years == pytest.approx(summed_window)

# Ensure integration rejects curves without observations.
def test_integrate_step_rejects_empty():
    with pytest.raises(ValueError):
        integrate_step([], [], 0, 1, 1)

# Ensure every curve time must have a corresponding value.
def test_integrate_step_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        integrate_step([1, 2], [0.8], 0, 2, 1)

# Ensure integration rejects a window with no positive duration.
def test_integrate_step_rejects_invalid_interval():
    with pytest.raises(ValueError):
        integrate_step([1, 2], [0.8, 0.6], 1, 1, 1)

# Ensure integration cannot extend beyond the final recorded time.
def test_integrate_step_rejects_extrapolation():
    with pytest.raises(ValueError):
        integrate_step([1, 2], [0.8, 0.6], 0, 3, 1)

# Ensure conditional years cannot be calculated after estimated survival reaches zero.
def test_summarise_years_rejects_zero_survival():
    table = aalen_johansen([1, 2, 3], [1, 1, 1])
    with pytest.raises(ValueError, match = "Cannot condition"):
        summarise_years(table, 3, 4)

# Check a cohort without deaths lives the entire restricted window with no cause losses.
def test_summarise_years_all_censored():
    table = aalen_johansen([1, 2, 3], [0, 0, 0])
    summary = summarise_years(table, 0, 3)
    assert summary["years_lived"] == pytest.approx(3.0)
    assert summary["years_lost_by_cause"] == {}

# Check conditional years on an age timescale with delayed participant entry.
def test_summarise_years_with_age_and_entry():
    table =aalen_johansen([52, 54, 55], [1, 2, 0], [50, 50, 53])
    summary = summarise_years(table, 52, 55)
    summed_window = summary["tau"] - summary["start"]
    summed_years = summary["years_lived"] + summary["years_lost_by_cause"]["cif_1"] + summary["years_lost_by_cause"]["cif_2"]
    assert summary["years_lived"] == pytest.approx(2.5)
    assert summary["years_lost_by_cause"]["cif_1"] == pytest.approx(0.0)
    assert summary["years_lost_by_cause"]["cif_2"] == pytest.approx(0.5)
    assert summed_years == pytest.approx(summed_window)

# Check weighted year totals partition the window and differ from unweighted totals.
def test_summarise_years_weighted():
    table_1 = aalen_johansen([1, 2, 3], [1, 2, 0], weights = [2, 1, 3])
    summary = summarise_years(table_1, 0, 3)
    summed_years = summary["years_lived"] + summary["years_lost_by_cause"]["cif_1"] + summary["years_lost_by_cause"]["cif_2"]
    assert summary["years_lived"] == pytest.approx(13/6)
    assert summary["years_lost_by_cause"]["cif_1"] == pytest.approx(2/3)
    assert summary["years_lost_by_cause"]["cif_2"] == pytest.approx(1/6)
    assert summed_years == pytest.approx(3.0)
    table_2 = aalen_johansen([1, 2, 3], [1, 2, 0])
    summary = summarise_years(table_2, 0, 3)
    assert summary["years_lived"] == pytest.approx(2.0)