from deaths_warrant.km import event_table, kaplan_meier; import pytest
from lifelines import KaplanMeierFitter

# Check risk-set and death counts when a death and censoring share an exit time.
def test_event_table():
    table = event_table([1, 2, 2, 3, 4], [1, 1, 0, 1, 0])
    assert table["time"].tolist() == [1, 2, 3, 4]
    assert table["at_risk"].tolist() == [5, 4, 2, 1]
    assert table["deaths"].tolist() == [1, 1, 1, 0]

# Check the survival steps against a hand-calculated tied-exit example.
def test_kaplan_meier():
    table = kaplan_meier([1, 2, 2, 3, 4], [1, 1, 0, 1, 0])
    assert table["time"].tolist() == [1, 2, 3, 4]
    assert table["survival"].tolist() == pytest.approx([0.8, 0.6, 0.3, 0.3])

# Compare survival at each exit time with lifelines' Kaplan-Meier estimate.
def test_kaplan_meier_matches_lifelines():
    table = kaplan_meier([1, 2, 2, 3, 4], [1, 1, 0, 1, 0])
    reference = KaplanMeierFitter().fit([1, 2, 2, 3, 4], event_observed=[1, 1, 0, 1, 0])
    expected = reference.predict(table["time"]).tolist()
    assert table["survival"].tolist() == pytest.approx(expected)

# Ensure survival remains one when no deaths occur.
def test_kaplan_meier_all_censored():
    table = kaplan_meier([1, 2, 3], [0, 0, 0])
    assert table["survival"].tolist() == pytest.approx([1, 1, 1])

# Ensure simultaneous deaths reduce survival using their combined count.
def test_kaplan_meier_tied_deaths():
    table = kaplan_meier([1, 1, 2], [1, 1, 0])
    assert table["time"].tolist() == [1, 2]
    assert table["survival"].tolist() == pytest.approx([1/3, 1/3])

# Ensure shuffled observations produce the same chronologically sorted survival steps.
def test_Kaplan_meier_unsorted():
    table = kaplan_meier([4, 2, 1, 3, 2], [0, 1, 1, 1, 0])
    assert table["time"].tolist() == [1, 2, 3, 4]
    assert table["survival"].tolist() == pytest.approx([0.8, 0.6, 0.3, 0.3])

# Check risk sets exclude participants until their entry time.
def test_event_table_delayed_entry():
    table = event_table([2, 4, 5], [1, 1, 0], [0, 0, 3])
    assert table["time"].tolist() == [2, 4, 5]
    assert table["at_risk"].tolist() == [2, 2, 1]
    assert table["deaths"].tolist() == [1, 1, 0]

# Check survival probabilities when follow-up begins at different times.
def test_kaplan_meier_delayed_entry():
    table = kaplan_meier([2, 4, 5], [1, 1, 0], [0, 0, 3])
    assert table["time"].tolist() == [2, 4, 5]
    assert table["survival"].tolist() == pytest.approx([0.5, 0.25, 0.25])

# Compare delayed-entry survival with lifelines' reference estimate.
def test_kaplan_meier_delayed_entry_matches_lifelines():
    table = kaplan_meier([2, 4, 5], [1, 1, 0], [0, 0, 3])
    reference = KaplanMeierFitter().fit([2, 4, 5], event_observed = [1, 1, 0], entry = [0, 0, 3])
    expected = reference.predict(table["time"]).tolist()
    assert table["survival"].tolist() == pytest.approx(expected)

# Ensure unequal time and event array lengths are rejected.
def test_event_table_rejects_mismatched_events():
    with pytest.raises(ValueError):
        event_table([2, 4], [1])

# Ensure each observation must have a corresponding entry time.
def test_event_table_rejects_mismatched_entry():
    with pytest.raises(ValueError):
        event_table([2, 4], [1, 0], [0])

# Ensure participants cannot enter at or after their own exit time.
def test_event_table_rejects_entry_at_or_after_exit():
    with pytest.raises(ValueError):
        event_table([2], [1], [2])
    with pytest.raises(ValueError):
        event_table([2], [1], [3])

# Ensure entry at another participant's death time does not inflate that risk set.
def test_event_table_entry_at_death_time():
    table = event_table([2, 4, 5], [1, 1, 0], [0, 0, 2])
    assert table["at_risk"].tolist() == [2, 2, 1]

# Check risk-set and death totals use participant weights rather than row counts.
def test_event_table_weighted():
    table = event_table([1, 2, 3], [1, 1, 0], weights = [2, 1, 3])
    assert table["time"].tolist() == [1, 2, 3]
    assert table["at_risk"].tolist() == pytest.approx([6.0, 4.0, 3.0])
    assert table["deaths"].tolist() == pytest.approx([2.0, 1.0, 0.0])

# Compare weighted survival with lifelines' reference estimate.
def test_kaplan_meier_weighted_matches_lifelines():
    table = kaplan_meier([1, 2, 3], [1, 1, 0], weights = [2, 1, 3])
    reference = KaplanMeierFitter().fit([1, 2, 3], event_observed = [1, 1, 0], weights = [2, 1, 3])
    expected = reference.predict(table["time"]).tolist()
    assert table["survival"].tolist() == pytest.approx(expected)

# Ensure each observation must have a corresponding weight.
def test_event_table_rejects_mismatched_weights():
    with pytest.raises(ValueError):
        event_table([1, 2], [1, 0], weights = [1])

@pytest.mark.parametrize(
        "bad_weight",
        [0, -1, float("nan"), float("inf"), -float("inf")],
)
# Ensure zero, negative and nonfinite weights are rejected.
def test_event_table_rejects_invalid_weight(bad_weight):
    with pytest.raises(ValueError):
        event_table([1], [1], weights = [bad_weight])