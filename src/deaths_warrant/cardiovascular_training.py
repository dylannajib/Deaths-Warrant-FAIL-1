"""Offline broad cardiovascular fitting and censored-outcome assessment."""

from math import exp; import warnings
import numpy as np; import pandas as pd
from lifelines import KaplanMeierFitter, WeibullAFTFitter, WeibullFitter
from lifelines.exceptions import ConvergenceError, ConvergenceWarning, StatisticalWarning
from lifelines.utils import concordance_index
from deaths_warrant.cardiovascular_data import DEVELOPMENT_CYCLES, FINAL_CYCLE
from deaths_warrant.cardiovascular_prognosis import FEATURES, FLAGS, MEASUREMENTS, MODEL_VERSION, validate_model

FORMULA = "ageYears + C(recordedSex) + " + " + ".join(FLAGS + MEASUREMENTS)
COEFFICIENTS = ["Intercept", "ageYears", "C(recordedSex)[T.2]"] + FLAGS + MEASUREMENTS
SEED = 20261027
PENALIZER = 0.01
PROTOCOL = {"version": "cardiovascular-assessment-v1", "candidate": "unweighted_weibull_aft",
    "formula": FORMULA, "penalizer": PENALIZER, "seed": SEED, "bootstrapSamples": 100,
    "selection": "Fixed unweighted candidate; normalised examination weights are sensitivity only, not used to select the winner.",
    "baselines": ["exponential", "weibull"], "horizons": [1, 3, 5],
    "primaryMetric": "five-year IPCW Brier error versus both training-fitted baselines",
    "censoring": "Unweighted training Kaplan–Meier censoring distribution; assumes independent censoring.",
    "finalCycle": FINAL_CYCLE, "clinicalRelease": False,
    "lifetime": "Weibull mean extrapolation is not validated by five-year error or concordance."}

# Check prepared input values before allowing them into fitting or evaluation.
def validate_table(table):
    required = FEATURES + ["follow_up_years", "death", "examWeight2yr", "seqn", "cycle"]
    if table.empty or not set(required).issubset(table.columns):
        raise ValueError("Prepared model data must contain participants and all required fields")
    numeric = table[FEATURES + ["follow_up_years", "death", "examWeight2yr", "seqn"]]
    if not all(pd.api.types.is_numeric_dtype(numeric[name]) for name in numeric) or not np.isfinite(numeric.to_numpy(dtype = float)).all():
        raise ValueError("Prepared model inputs must be finite numbers")
    if not table[FLAGS + ["death"]].isin([0, 1]).all().all() or not table["recordedSex"].isin([1, 2]).all():
        raise ValueError("Invalid binary history, mortality or recorded-sex code")
    if not table["ageYears"].between(40, 79).all() or not table["ageYears"].mod(1).eq(0).all():
        raise ValueError("Prepared ages must be completed years from 40 to 79")
    if not table[["heartFailure", "coronaryHeartDisease", "angina", "previousHeartAttack", "previousStroke"]].eq(1).any(axis = 1).all():
        raise ValueError("Each participant requires a supported cardiovascular history")
    if not (table[MEASUREMENTS + ["follow_up_years", "examWeight2yr", "seqn"]] > 0).all().all() or table["seqn"].duplicated().any():
        raise ValueError("Measurements, time, weights and unique IDs must be positive")
    return table

# Fit the fixed formula, optionally checking sensitivity to normalised examination weights.
def fit_candidate(table, weighted = False):
    validate_table(table)
    fitting = table[FEATURES + ["follow_up_years", "death"]].copy()
    arguments = {}
    if weighted:
        fitting["fitWeight"] = table["examWeight2yr"].to_numpy() / table["examWeight2yr"].mean()
        arguments = {"weights_col": "fitWeight", "robust": True}
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        warnings.simplefilter("ignore", StatisticalWarning)
        return WeibullAFTFitter(penalizer = PENALIZER).fit(fitting, duration_col = "follow_up_years",
            event_col = "death", formula = FORMULA, **arguments)

# Convert lifelines coefficients to the fixed standard-library inference representation.
def parameters(fitter):
    return {"coefficients": [float(fitter.params_.loc[("lambda_", name)]) for name in COEFFICIENTS],
        "shape": exp(float(fitter.params_.loc[("rho_", "Intercept")]))}

# Fit reproducible ordinary-bootstrap samples without reading validation or final outcomes.
def export_model(training, fitter, samples = 100, seed = SEED):
    if type(samples) is not int or samples < 30:
        raise ValueError("At least thirty bootstrap samples are required")
    random = np.random.default_rng(seed)
    bootstrap = []
    for _ in range(samples):
        sample = training.iloc[random.integers(0, len(training), len(training))].reset_index(drop = True).copy()
        # Resampled rows deliberately repeat people; temporary unique IDs permit input checks.
        sample["seqn"] = np.arange(1, len(sample) + 1)
        try:
            bootstrap.append(parameters(fit_candidate(sample)))
        except (ConvergenceError, ConvergenceWarning, ValueError, ArithmeticError):
            continue
    if len(bootstrap) < max(30, 0.9 * samples):
        raise ValueError("Too many bootstrap fits failed; candidate must not be exported")
    return validate_model({"schemaVersion": 1, "modelVersion": MODEL_VERSION, "status": "experimental",
        "features": list(FEATURES), "parameters": parameters(fitter), "bootstrapSamples": bootstrap,
        "measurementRanges": {name: [float(training[name].min()), float(training[name].max())] for name in MEASUREMENTS},
        "training": {"participants": len(training), "deaths": int(training["death"].sum()), "weighted": False,
            "penalizer": PENALIZER, "seed": seed, "bootstrapRequested": samples, "bootstrapSuccessful": len(bootstrap)},
        "protocol": PROTOCOL})

# Evaluate the censoring survival immediately before an event or at a horizon.
def censoring_survival(fitter, times, before = False):
    curve = fitter.survival_function_.iloc[:, 0]
    positions = np.searchsorted(curve.index.to_numpy(), times, side = "left" if before else "right") - 1
    return np.where(positions < 0, 1.0, curve.to_numpy()[np.maximum(positions, 0)])

# Score survival predictions without incorrectly counting early censoring as survival.
def brier_score(training, checking, predictions, horizon):
    times = checking["follow_up_years"].to_numpy()
    deaths = checking["death"].to_numpy()
    predicted = np.asarray(predictions, dtype = float)
    if predicted.shape != times.shape or not np.isfinite(predicted).all() or ((predicted < 0) | (predicted > 1)).any():
        raise ValueError("Brier predictions must be finite probabilities, one per participant")
    censoring = KaplanMeierFitter().fit(training["follow_up_years"], event_observed = 1 - training["death"])
    died = (times <= horizon) & (deaths == 1)
    alive = times > horizon
    weights = np.zeros(len(checking))
    event_g = censoring_survival(censoring, times[died], before = True)
    horizon_g = float(censoring_survival(censoring, np.array([horizon]))[0])
    if (event_g <= 0).any() or horizon_g <= 0:
        raise ValueError("Censoring support does not extend to this assessment horizon")
    weights[died] = predicted[died] ** 2 / event_g
    weights[alive] = (1 - predicted[alive]) ** 2 / horizon_g
    return float(weights.mean())

# Compare a frozen fit with both simple baselines on distinct checking participants.
def evaluate_candidate(fitter, training, checking):
    validate_table(training); validate_table(checking)
    if set(training["seqn"]) & set(checking["seqn"]):
        raise ValueError("Training and checking participant IDs must not overlap")
    if training["death"].sum() == 0 or checking["death"].sum() == 0:
        raise ValueError("Training and checking require recorded deaths")
    baseline_mean = float(training["follow_up_years"].sum() / training["death"].sum())
    baseline = WeibullFitter().fit(training["follow_up_years"], event_observed = training["death"])
    observed = KaplanMeierFitter().fit(checking["follow_up_years"], event_observed = checking["death"])
    predictions = fitter.predict_survival_function(checking, times = [1, 3, 5])
    horizons = {}
    for year in [1, 3, 5]:
        probabilities = predictions.loc[year].to_numpy()
        exponential = exp(-year / baseline_mean)
        weibull = float(baseline.survival_function_at_times([year]).iloc[0])
        horizons[str(year)] = {"meanPredictedSurvival": float(probabilities.mean()),
            "observedKaplanMeierSurvival": float(observed.predict(year)),
            "brier": brier_score(training, checking, probabilities, year),
            "exponentialBrier": brier_score(training, checking, np.full(len(checking), exponential), year),
            "weibullBrier": brier_score(training, checking, np.full(len(checking), weibull), year),
            "deathsByHorizon": int(((checking["death"] == 1) & (checking["follow_up_years"] <= year)).sum()),
            "earlyCensored": int(((checking["death"] == 0) & (checking["follow_up_years"] <= year)).sum())}
    concordance = float(concordance_index(checking["follow_up_years"], fitter.predict_expectation(checking), checking["death"]))
    outside = pd.Series(False, index = checking.index)
    for name in MEASUREMENTS:
        outside |= ~checking[name].between(training[name].min(), training[name].max())
    return {"participants": len(checking), "deaths": int(checking["death"].sum()), "horizons": horizons,
        "concordance": concordance, "outsideTrainingMeasurementRanges": int(outside.sum()),
        "baselineMeanYears": baseline_mean, "assessment": "Statistical checks only; lifetime extrapolation and clinical input equivalence remain unvalidated."}

# Prevent accidental final-cycle use or participant leakage during development.
def validate_development_split(training, validation):
    validate_table(training); validate_table(validation)
    if not training["cycle"].isin(DEVELOPMENT_CYCLES).all() or not validation["cycle"].isin(DEVELOPMENT_CYCLES).all():
        raise ValueError("Reserved or unsupported cycle cannot enter development")
    if set(training["seqn"]) & set(validation["seqn"]):
        raise ValueError("Training and validation participants must be distinct")
