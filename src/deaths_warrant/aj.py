from deaths_warrant.km import event_table; import pandas as pd

# Accumulate weighted cause-specific incidence and overall survival at each exit time.
def aalen_johansen(times, causes, entry=None, weights=None):
    events = []
    for cause in causes:
        if cause == 0:
            events.append(0)
        else:
            events.append(1)
    if weights is None:
        weights = [1.0] * len(times)
    table = event_table(times, events, entry, weights=weights)
    cause_codes = []
    for cause in sorted(set(causes)):
        if cause != 0:
            cause_codes.append(cause)
    cif = {}
    for cause in cause_codes:
        cif[cause] = 0.0
    survival = 1.0
    rows = []
    for row in table.itertuples(index=False):
        for cause in cause_codes:
            deaths_from_cause = 0.0
            for duration, observed_cause, weight in zip(times, causes, weights):
                if duration == row.time and observed_cause == cause:
                    deaths_from_cause += weight
            cif[cause] += survival * deaths_from_cause / row.at_risk
        survival *= 1 - row.deaths / row.at_risk
        result = {"time": row.time, "survival": survival}
        for cause in cause_codes:
            result[f"cif_{cause}"] = cif[cause]
        rows.append(result)
    return pd.DataFrame(rows)