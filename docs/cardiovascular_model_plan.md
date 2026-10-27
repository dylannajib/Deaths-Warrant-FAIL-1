# One broad cardiovascular model: preparation and fixed assessment plan

Version: `cardiovascular-data-v1`, fixed before fitting the new model. Preparation itself performs no fitting. The broad candidate has now been fitted, frozen and checked; results are recorded in `models/cardiovascular/README.md` and the aggregate evaluation artifacts.

## 1. Supported patient and output

- Goal: mean remaining years from one baseline assessment, considering death from any cause. Survival probabilities over 1, 3 and 5 years are checks, not substitutes for that goal.
- Initial population: examined NHANES participants with recorded interview age 40–79 and at least one reported history of heart failure, coronary heart disease, angina, heart attack or stroke. Multiple histories remain separate columns in one model.
- The age restriction avoids treating top-coded 80+ ages as exact ages and limits sparse younger cases. Age is completed years recorded at interview, carried into the subsequent examination snapshot; exact adult examination age is not reconstructed.
- Not all cardiovascular disease is covered: these data do not establish support for isolated arrhythmias, valve disease or other diagnoses absent from the five history questions. The model does not distinguish heart-failure subtype or severity, or stroke subtype.
- Start follow-up at the examination, using `permth_exm`, because blood pressure, BMI and blood sampling occur at the examination. Interview measurements precede the examination. Do not use interview follow-up with the later examination measurements.
- Intended outputs are conditional statistical estimates, not an exact death date, condition-attributed years or treatment effects. Lifetime extrapolation will require explicit assumptions and assessment in later steps.

## 2. Dataset and preparation

Source: public NHANES development cycles **2007–2008, 2011–2012, 2013–2014**, linked to the **2019 public mortality release**. The earlier heart-failure work used parts of 2011–2014; those cycles are development data here, not independent final validation.

Use public files for statistical model development under the [NCHS Data User Agreement](https://www.cdc.gov/nchs/policy/data-user-agreement.html). No identification, individually identifiable linkage or participant contact is attempted. Public data access does not establish clinical suitability or blanket approval for patient deployment.

### Predictor dictionary

| Prepared field | Source | Definition / units |
| --- | --- | --- |
| `ageYears` | DEMO `RIDAGEYR` | Completed interview age, 40–79 |
| `recordedSex` | DEMO `RIAGENDR` | Recorded demographic code 1=male, 2=female; two categories, not an inferred identity or automatic mapping from FHIR gender |
| `heartFailure` | MCQ `MCQ160B` | Ever told had congestive heart failure |
| `coronaryHeartDisease` | MCQ `MCQ160C` | Ever told had coronary heart disease |
| `angina` | MCQ `MCQ160D` | Ever told had angina |
| `previousHeartAttack` | MCQ `MCQ160E` | Ever told had heart attack |
| `previousStroke` | MCQ `MCQ160F` | Ever told had stroke |
| `diabetes` | DIQ `DIQ010` | Told had diabetes: 1=yes, 2=no; borderline, refused, unknown and missing remain missing |
| `currentSmoker` | SMQ `SMQ020`, `SMQ040` | Established cigarette-smoking definition: at least 100 lifetime cigarettes and now daily/some-day smoking; never-100 or former established smokers are 0. Unknown stays missing; this is not all tobacco/nicotine use |
| `bmi` | BMX `BMXBMI` | kg/m² |
| `systolicBloodPressure` | BPX `BPXSY1`–`BPXSY4` | Arithmetic mean of available positive readings, mmHg; no valid reading remains missing |
| `creatinine` | BIOPRO `LBXSCR` | Serum creatinine, mg/dL; use the published standardised release without applying the 2007 adjustment a second time |

All five condition indicators use 1=yes, 0=no; questionnaire response 2 is mapped to 0. Refused/unknown/missing answers never become no. Conditions describe reported histories, not the underlying cause of death.

Unknown predictors are excluded by a fixed complete-case rule before the internal split, with counts by feature. No medians or other fitted preprocessing are calculated from validation data. This simple first rule can introduce selection bias and means a future record with missing required inputs cannot yet receive an estimate.

Negative/infinite measurements and invalid source codes raise errors. Zero measurements are unusable; zero follow-up is reported and excluded rather than replaced by invented time. Participant IDs must be finite integers and unique. Sources merge one-to-one; missing mortality-linkage records raise errors.

### Outcome and metadata

- `follow_up_years = permth_exm / 12`; `death = mortstat` (1=death from any cause, 0=observation ended without a recorded death).
- `cycle`, `seqn`, `examWeight2yr`, `psu` and `stratum` are metadata, not predictors. Neither follow-up nor death may enter the predictor formula.
- The MEC examination weight is retained because examination measurements are used. Whole-development pooled weights can be constructed from the three two-year MEC weights following CDC guidance. An internal split changes sampling again; do not label unadjusted split weights or resulting counts as nationally representative.
- Step 4 starts with an unweighted sample baseline. Weighting choices for the broad candidate and sensitivity checks must be recorded before final checking. A naive bootstrap or ordinary standard error does not account for the full NHANES survey design.

### Actual preparation counts

| Cycle | Reported CVD histories in eligible examined/linked ages | Missing-predictor exclusions | Included | Recorded deaths |
| --- | ---: | ---: | ---: | ---: |
| 2007–2008 | 508 | 117 | 391 | 173 |
| 2011–2012 | 404 | 92 | 312 | 85 |
| 2013–2014 | 420 | 68 | 352 | 61 |
| Total | 1332 | 277 | 1055 | 319 |

No eligible reported-CVD record had zero follow-up in this run. Exclusion counts are not additive across missing-feature categories because one person can lack several inputs. The full machine-readable audit and source checksums are in `models/cardiovascular/data_summary.json`.

## 3. Fixed separation of development and final checking

- Internal **training**: 838 participants, 255 recorded deaths.
- Internal **validation**: 217 participants, 64 recorded deaths. Use this for development comparisons; it is not the final untouched sample.
- Assignment uses SHA-256 of seed `20261027`, cycle and participant ID: approximately 80/20. It is stable across row order, does not use outcomes and does not change when a result is disappointing. IDs do not overlap between splits.
- **Final checking: reserve the entire 2009–2010 cycle.** At preparation time its source files and outcomes were unopened. It was subsequently opened only after the candidate and protocol were frozen. Development source selection still rejects this cycle. The completed separate-period check contains 389 participants and 134 deaths; do not reuse it for tuning this candidate.
- The reserved cycle has potential mortality follow-up beyond five years. It is earlier than some development records: this is a separate-period check, not a forward-temporal or separate-clinical-population validation.
- The candidate, preprocessing, weights and comparison rules were frozen before final access. The script now preserves a durable start marker before any future reserved access, blocks concurrent runs and prevents development overwrites once final checking begins. Checking outcomes and changing the model in response would turn this sample into development data.

## Rebuild and file locations

From the repository root:

```bash
.venv/bin/python scripts/prepare_cardiovascular.py
```

This downloads/caches official CDC development files only, with HTTPS checks, size limits and format checks. It records each file's URL and SHA-256. It never downloads a model executable or runs downloaded code.

- `data/processed/cardiovascular/training.csv` — ignored participant rows.
- `data/processed/cardiovascular/validation.csv` — ignored participant rows.
- `data/processed/cardiovascular/manifest.json` — ignored local copy of the preparation audit.
- `models/cardiovascular/data_summary.json` — aggregate counts, source provenance and fixed split plan; no participant rows.
- `src/deaths_warrant/cardiovascular_data.py` — `development_sources()`, `fetch_source()`, `make_cardiovascular_table()`, `prepare_development_cycle()`, `split_development()`.
- `scripts/prepare_cardiovascular.py` — orchestration only; no import-time download or model fitting.

Do not commit the CSVs or raw data. Existing heart-failure model artifacts are retained as earlier experiments. `data_summary.json` is the historical preparation snapshot; `final_evaluation.json` records subsequent reserved-data access and results.

## Model implementation

`scripts/cardiovascular_model.py` fits the fixed twelve-input Weibull AFT formula with penalizer 0.01, compares exponential and Weibull baselines, records normalised examination-weight sensitivity, and exports 100 ordinary-bootstrap fits. Validation and final checks report 1/3/5-year survival, IPCW Brier error using the training censoring distribution, and concordance. The unweighted candidate was fixed before final access; sensitivity results did not select a replacement. `freeze.json` records the candidate fingerprint, prepared-data hashes and comparison protocol. See the model README for the completed results and execution commands.

## Source documentation

- [Medical conditions](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2007/DataFiles/MCQ_E.htm)
- [Blood-pressure protocol](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2007/DataFiles/BPX_E.htm)
- [2007–2008 published creatinine standardisation](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2007/DataFiles/BIOPRO_E.htm)
- [2011–2012 biochemistry](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2011/DataFiles/BIOPRO_G.htm) and [2013–2014 biochemistry](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2013/DataFiles/BIOPRO_H.htm)
- [Diabetes questionnaire](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2007/DataFiles/DIQ_E.htm) and [smoking questionnaire](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2007/DataFiles/SMQ_E.htm)
- [Public linked mortality files](https://www.cdc.gov/nchs/linked-data/mortality-files/index.html)
- [Combining survey cycles and weights](https://wwwn.cdc.gov/nchs/nhanes/tutorials/weighting.aspx)
