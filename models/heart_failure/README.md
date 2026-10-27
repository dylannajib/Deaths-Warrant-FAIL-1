# Experimental NHANES heart-failure model

This model is not clinically validated and failed to improve five-year prediction error over its baseline. Do not use it for patient prognosis or end-of-life planning. The website does not load it yet.

## Rebuild

From the repository root, with the Linux environment installed:

```bash
.venv/bin/python scripts/train_heart_failure.py
```

Requires the ignored local files `MCQ_G.xpt`, `DEMO_G.xpt`, `NHANES_2011_2012_MORT_2019_PUBLIC.dat`, `MCQ_H.xpt`, `DEMO_H.xpt` and `NHANES_2013_2014_MORT_2019_PUBLIC.dat` in `data/raw/`. Download the XPT files from the CDC NHANES public data pages and the mortality files from the CDC linked-mortality directory. Do not commit participant records.

The command writes `model.json` (aggregate fitted settings and bootstrap fits) and `evaluation.json` (aggregate development checks). It never exports participant rows. It uses seed `20261027`, 100 bootstrap samples, the pinned Python dependencies in `pyproject.toml`, a fixed Weibull model and penalizer 0.01. At least 90% of bootstrap fits, and at least 30 fits, must succeed; otherwise no model is written. Small floating-point differences across platforms are possible.

The fixed features are age in decades relative to 60, previous heart attack and previous stroke. Shape is shared across participants. Training uses complete histories from eligible 40–79-year-olds reporting heart failure in 2011–2012: **128 participants, 54 deaths**. One participant with unknown heart-attack history is excluded, including their recorded death. The checking cycle is 2013–2014: **128 participants, 38 total deaths**, of which **29** occur by five years.

Fits and bootstrap resampling are unweighted and do not account for NHANES survey design. The ordinary bootstrap interval describes variation in the fitted conditional mean under this model, not a patient's personal remaining-life range. It does not account for model misspecification, clinical-record versus survey differences, treatment changes or uncertain lifetime extrapolation.

## Research-only inference

```python
from deaths_warrant.prognosis import load_model, predict_prognosis

model = load_model("models/heart_failure/model.json")
profile = {
    "asOf": "2026-01-01", "ageYears": 60, "heartFailure": True,
    "previousHeartAttack": True, "previousStroke": False
}
result = predict_prognosis(profile, model, research_mode=True)
```

Omitting the research flag raises an error. Inference uses the standard library only and does not fit models, access files other than the explicitly loaded artifact, make network requests or save patient inputs.

`remainingYears` is the mean implied by the fitted Weibull curve extending beyond follow-up. `survivalByYear` contains probabilities at 1, 3 and 5 years. `meanUncertainty` is a percentile interval from bootstrap fits, when at least 30 samples are available. Every result carries experimental status and explicit warnings. No treatment effects or condition-attributed losses are returned.

## Current decision

The multivariable candidate has five-year Brier error approximately **0.182847**, versus **0.175546** for a Weibull baseline fitted to the same participants without medical predictors. Concordance is approximately **0.483135**. Lower Brier error is better; concordance near 0.5 is chance-level ranking.

This comparison is development evidence. It has not established patient-level accuracy, lifetime accuracy, population-representative estimates or a statistically reliable difference between models. The candidate is retained to make the experiment reproducible, not because it is suitable for release. See `docs/prognosis_inputs.md` for the supported input subset and evidence still required.
