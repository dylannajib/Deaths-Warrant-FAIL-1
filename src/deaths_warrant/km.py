from math import isfinite; import pandas as pd

# Count weighted risk sets and deaths at each exit time, allowing delayed entry.
def event_table(times, events, entry=None, weights=None):
    rows = []
    if entry is None:
        entry = [0] * len(times)
    if weights is None:
        weights = [1.0] * len(times)
    if not (len(times) == len(events) == len(entry) == len(weights)):
        raise ValueError("Lengths of times, events, entry and weights must be the same")
    for weight in weights:
        if not (isfinite(weight) and weight > 0):
            raise ValueError("Weight must be finite and strictly positive")
    for entry_time, exit_time in zip(entry, times):
        if entry_time >= exit_time:
            raise ValueError("Entry time cannot be greater than or equal to exit time")
    for t in sorted(set(times)):
        at_risk = 0.0
        deaths = 0.0
        for duration, event, entry_time, weight in zip(times, events, entry, weights):
            if duration >= t and entry_time < t:
                at_risk += weight
            if duration == t and event == 1:
                deaths += weight
        rows.append({"time": t, "at_risk": at_risk, "deaths": deaths})
    return pd.DataFrame(rows)

# Multiply conditional survival probabilities across the weighted event table.
def kaplan_meier(times, events, entry=None, weights=None):
    table = event_table(times, events, entry, weights=weights)
    survival = 1.0
    rows = []
    for row in table.itertuples(index=False):
        survival = survival * (1 - row.deaths/row.at_risk)
        rows.append({"time": row.time, "survival": survival})
    return pd.DataFrame(rows)