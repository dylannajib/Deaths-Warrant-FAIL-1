from deaths_warrant.km import event_table; import pandas as pd

def remove_cause(times, causes, cause_to_remove, entry=None, weights=None):
    if cause_to_remove == 0:
        raise ValueError("Cause to remove cannot be censored")
    events = []
    for cause in causes:
        if cause == 0:
            events.append(0)
        else:
            events.append(1)
    if weights is None:
        weights = [1.0] * len(times)
    table = event_table (times, events, entry, weights)
    survival = 1.0
    rows = []
    for row in table.itertuples(index=False):
        removed_deaths = 0.0
        for duration, observed_cause, weight in zip(times, causes, weights):
            if duration == row.time and observed_cause == cause_to_remove:
                removed_deaths += weight
        remaining_deaths = row.deaths - removed_deaths
        survival = survival * (1 - remaining_deaths/row.at_risk)
        rows.append({"time": row.time, "survival": survival})
    curve = pd.DataFrame(rows)
    return({
        "curve": curve, "removed_cause": cause_to_remove, "assumption_dependent": True,
        "warning": "Assumption-dependent scenario: assumes independent latent cause-specific failure times and unchanged hazards for remaining causes. Not a causal prediction"
    })