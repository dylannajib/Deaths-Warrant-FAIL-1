# Integrate a step curve over the requested window without extrapolating past observations.
def integrate_step(times, values, start, tau, initial_value):
    if not (len(times) == len(values)):
        raise ValueError("Lengths of times and values must be equal (integrate step)")
    if not (times) or not (values):
        raise ValueError("Times and values cannot be blank (integrate step)")
    if tau <= start:
        raise ValueError("Tau cannot be lesser or equal to start (integrate step)")
    if tau > times[-1]:
        raise ValueError("Tau cannot exceed the final recorded time (integrate step)")
    area = 0.0
    current_time = start
    current_value = initial_value
    for time, value in zip(times, values):
        if time <= start:
            current_value = value
            continue
        if time >= tau:
            break
        else:
            area += (time - current_time)*(current_value)
            current_time = time
            current_value = value
    area += (tau - current_time)*(current_value)
    return(area)

# Calculate restricted years lived and cause-specific years lost conditional on survival at start.
def summarise_years(table, start, tau):
    cause_columns = []
    for cause in table.columns:
        if cause.startswith("cif_"):
            cause_columns.append(cause)
    survival_at_start = 1.0
    cif_at_start = {}
    for cause in cause_columns:
        cif_at_start[cause] = 0.0
    prior = table.loc[table["time"] <= start]
    if not prior.empty:
        baseline = prior.iloc[-1]
        survival_at_start = baseline["survival"]
        for cause in cause_columns:
            cif_at_start[cause] = baseline[cause]
    if survival_at_start <= 0:
        raise ValueError("Cannot condition on survival when its estimated probability is 0")
    window = tau - start
    curve_times = table["time"].tolist()
    survival_values = table["survival"].tolist()
    area = integrate_step(curve_times, survival_values, start, tau, 1)
    years_lived = area / survival_at_start
    years_lost_by_cause = {}
    for cause in cause_columns:
        current_cause = table[cause].tolist()
        cause_area = integrate_step(curve_times, current_cause, start, tau, 0)
        conditional_loss = (cause_area - (cif_at_start[cause] * window)) / survival_at_start
        years_lost_by_cause[cause] = conditional_loss
    return{"start": start, "tau": tau, "years_lived": years_lived, "years_lost_by_cause": years_lost_by_cause}
