# Milestone 11.1 decision — 2026-10-27

Assessment completed: **research calculations can continue; no assessed route currently supports patient remaining-years estimates for this project.** This closes the assessment with a negative result for the present candidate. It does not complete the product's prognosis requirement or approve a model.

## Product and population

The intended output remains mean remaining years from an individual patient's medical records, with understandable uncertainty. Treatment updates and years attributed to each condition require separate evidence. The current candidate uses ages 40–79, reported heart-failure history, age, previous heart attack and previous stroke. Input definitions and limitations are in `prognosis_inputs.md`.

## Routes assessed

| Route | Finding and decision |
| --- | --- |
| Own NHANES model | Reproducible research foundation. Three inputs fail to improve baseline error; lifetime and clinical-record accuracy are unvalidated. Retain the failed experiment; reject patient release. |
| Seattle Heart Failure Model | Publishes mean life expectancy, closest to the desired output. Website terms target knowledgeable healthcare providers and do not establish our redistribution/patient-facing implementation permission. Candidate only after suitable permission and implementation/validation evidence. |
| MAGGIC | Established mortality-risk work using clinical inputs. The cited study does not establish our remaining-lifetime output or redistribution permissions for copied implementation assets. Potential benchmark, not a substitute for remaining years. |
| HF-ACTION | More clinical detail but a selected historical trial population. Formal access, consent restrictions and an agreement apply; no approved project access exists. Potential development source after suitable access and a research plan. |
| UCI Heart Failure Clinical Records | 299 patients, ejection fraction and creatinine; repository specifies CC BY 4.0. Open access does not establish lifetime accuracy or treatment effects. Optional research benchmark, not a shortcut to patient life expectancy. |

This is a bounded review, not a claim that no suitable data/model exists anywhere. No access request, agreement acceptance or message to an owner was made.

## Measured result

Training: 128 complete 2011–2012 records, 54 deaths. Checking: 128 2013–2014 records, 29 deaths by five years. Personalised Brier error **0.1828472347**, baseline **0.1755460374** (lower is better); concordance **0.4831346690** (0.5 is chance-level ranking).

Independent final assessment, lifetime validation and survey-to-clinical-record validation are absent. These point estimates do not establish a statistically reliable difference. The implemented error/ranking checks are minimal rejection screens, not sufficient clinical acceptance criteria. Even improved development metrics cannot approve this experimental model.

## Function and output trace

Run `.venv/bin/python scripts/train_heart_failure.py` from the repository root:

1. `prepare_cycle()` links each cycle and explicitly excludes unknown histories.
2. `fit_research_model()` calls `fit_parameters()` and bootstrap fits using only training records.
3. `evaluate_model()` compares predictions with the same-sample baseline using checking records.
4. `model_fingerprint()` identifies the exact settings using a hash of canonical JSON.
5. `assess_feasibility()` checks report/model agreement and valid metrics, then records the research-only decision and failed checks.
6. The script writes aggregate `model.json`, `evaluation.json` and `feasibility.json` under `models/heart_failure/`. Participant rows are not exported.

The fingerprint detects accidental settings/report mismatches; it is not an authenticity signature or access control. `assess_feasibility()` accepts experimental models only and cannot approve clinical use.

`predict_prognosis()` rejects ordinary calls. Explicit `research_mode=True` invokes `validate_profile()`, `validate_model()` and `_estimate()`, returning experimental results and limitations. That flag is an opt-in, not authentication or a privacy boundary. Prognosis and the new clinical readers remain disconnected from the page pending 11.4.

## Security and verification

`Home.handleFileChange()` now invokes `validatePatientFile()` before `file.text()`, rejecting unsupported, empty and over-10-MiB records. Existing `parseCdaXml()` rejects document-type/entity declarations before DOM parsing. No upload endpoint, external script or automatic storage was introduced.

Passed: **151 Python tests**, **59 frontend tests**, TypeScript, lint and static build. The production website was tested through the collaborative browser on loopback port 8001: valid FHIR/CCD; wrong reference; missing Patient; malformed JSON/XML; empty, unsupported and oversized files; XML entity declaration; recovery. The input recovered after errors. No additional resource requests were observed during the recorded import tests. This is scoped evidence, not the final 11.5 privacy/security audit or browser prognosis testing.

## Required before patient prognosis

Obtain permitted clinical/outcome data or a suitable published-model route; establish fit to the target patients and remaining-years output; predefine the assessment protocol and reserve independent data; review clinical mappings, treatment claims, uncertainty and lifetime assumptions. More implementation code cannot supply external permissions or missing outcome evidence.

## Primary sources checked

- [NHANES questionnaire](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2011/DataFiles/MCQ_G.htm)
- [SHFM life expectancy](https://depts.washington.edu/shfm/update.php) and [website terms](https://depts.washington.edu/shfm/EULA.php)
- [Original MAGGIC study](https://pubmed.ncbi.nlm.nih.gov/23095984/)
- [HF-ACTION](https://biolincc.nhlbi.nih.gov/studies/hf_action/) and [BioLINCC access](https://biolincc.nhlbi.nih.gov/faq/)
- [UCI dataset and licence](https://archive.ics.uci.edu/dataset/519/heart+failure+clinical+records) and [associated study](https://doi.org/10.1186/s12911-020-1023-5)
