# Broad cardiovascular research model

Version `nhanes-cardiovascular-weibull-0.1.0`. One model uses age, recorded sex, five cardiovascular histories, diabetes, established cigarette-smoking status, BMI, systolic blood pressure and creatinine. Adults 40–79 with at least one supported cardiovascular history are the defined population. This is a software research prototype, not a validated patient-prognosis model.

## Recorded checks

| Sample | Participants | Recorded deaths | Five-year Brier error | Exponential baseline | Weibull baseline | Concordance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Internal validation | 217 | 64 | 0.12510 | 0.13265 | 0.13200 | 0.66468 |
| Reserved 2009–2010 | 389 | 134 | 0.10977 | 0.11371 | 0.11094 | 0.67703 |

Lower Brier error is better. The final five-year improvement over the Weibull baseline is about 1.1%; it is modest, with no established uncertainty interval for that improvement. Three-year error is worse (0.06441 versus 0.06031 Weibull). Final mean predicted five-year survival is 84.62%, versus 87.40% observed. The final sample is an earlier survey period than some development data, not forward-temporal or clinical validation. Two validation and two final participants have measurements outside training support; evaluation includes them, but the inference API rejects such inputs.

Training uses 838 participants/255 deaths from 2007–2008, 2011–2012 and 2013–2014. Validation is separate, deterministic and outcome-independent. The unweighted candidate and full protocol were frozen before reserved data access. Normalised examination-weight sensitivity gave validation five-year error 0.12554 and concordance 0.66160; the unweighted candidate was retained as predefined, without claims of national representativeness. No final-data fitting or refitting on validation was performed.

The original final check finished before the durable interruption marker was introduced during review. Its `final_evaluation.json` already prevents candidate replacement. Subsequent runs also persist `final_started.json` before any reserved access, so failures cannot reopen development, and use an exclusive `.run.lock` to prevent concurrent writes. A crash may leave that transient lock: verify the process has ended before removing it. Do not remove final markers or reports to tune this version.

## Trace and files

1. `prepare_development_cycle()` → `make_cardiovascular_table()` → `split_development()` prepares ignored participant CSVs; `data_summary.json` preserves the historical preparation audit.
2. `validate_development_split()` → `fit_candidate()` → `evaluate_candidate()` performs internal comparisons. `brier_score()` accounts for early censoring rather than marking it as survival.
3. `export_model()` saves the main fit and 100 ordinary-bootstrap fits in `model.json`. `model_fingerprint()` binds the candidate to `freeze.json`; the freeze also hashes the prepared data.
4. The explicit `--final-check` path verifies the frozen fit/data/protocol before `prepare_final()` accesses the reserved period. `final_evaluation.json` contains aggregate provenance, exclusions and results, with no participant rows.
5. `load_model()` → `validate_profile()` → `predict_prognosis(..., research_mode = True)` calculates the Weibull mean and survival at 1/3/5 years using only Python's standard library. Coefficient order and numerical parity with lifelines are tested.

New fitting is invoked with `.venv/bin/python scripts/cardiovascular_model.py`; explicit final checking adds `--final-check`. The existing output directory is locked against retraining by its completed final report. Reproduction in another output directory is possible with `--output-dir`, but the already-inspected 2009–2010 outcomes cannot become untouched data again. Preserve the original results and avoid selecting changes based on that sample.

## Output meaning and limits

`remainingYears` is the model's mean lifetime beyond the assessment, including extrapolation past observed follow-up. Five-year checks do not validate that lifetime tail. `meanUncertainty` is a percentile interval over 100 ordinary-bootstrap fitted means, not the range in which an individual's death will occur. It omits survey-design, measurement and extrapolation uncertainty.

Complete-case exclusion, historical self-reports, missing current severity, clinical/survey input differences and external transport remain unresolved. No treatment effects or condition-attributed years are estimated. The output explicitly sets `clinicallyValidated`, `supportsTreatmentEffects` and `supportsConditionAttribution` to false. See `docs/cardiovascular_record_contract.md` for the deliberately narrow record-import subset.
