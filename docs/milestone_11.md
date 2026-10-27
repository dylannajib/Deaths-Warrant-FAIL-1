# Milestone 11: cardiovascular research prototype

The product goal is a remaining-years estimate from a patient's medical records. The current implementation checkpoint reaches experimental extraction and calculation code; it does not establish a suitable patient-prognosis model.

| Subgoal | Status |
| --- | --- |
| 11.1 — Model/data feasibility | **Research-prototype assessment complete.** Broad candidate frozen, weighting sensitivity recorded and reserved 2009–2010 check completed. Five-year error modestly improves over both baselines; three-year error does not. Lifetime accuracy and patient-prognosis suitability remain unestablished. See `models/cardiovascular/README.md`. |
| 11.2a — Basic import | Completed checkpoint: supported FHIR JSON and CCD XML structure/identity checks. |
| 11.2b — Clinical-field extraction | **Prototype subset complete.** Strict broad FHIR/CCD questionnaire snapshot readers return the same complete profile; ordinary EHR exports are not generally supported. See `cardiovascular_record_contract.md`. Existing HF readers are retained. |
| 11.3 — Prognosis calculations | **Research engine complete.** Versioned broad artifact, standard-library inference, fitted-mean bootstrap interval, support checks and parity tests implemented. Research acknowledgement remains required; no treatment or individual-condition attribution is claimed. |
| 11.4 — Browser calculation/results | Pending. Clinical readers and model are not connected to the page. |
| 11.5 — Privacy, performance and builds | Pending final milestone checks. Python/frontend automated checks are in CI; no final browser privacy audit, benchmark or deployment has been performed. |

Milestone 12 remains reserved for user-directed visual polishing.

## Checkpoint verification — 27 October 2026

- Python: 206 tests passed, including analytic survival examples, lifelines/export parity, shared clinical input, early-censoring/tie handling, numerical rejection and interrupted-final-check protection.
- Frontend: 142 tests passed; TypeScript, ESLint and static production build passed.
- Real browser: eight synthetic direct-reader checks passed (FHIR/CCD parity, duplicate identity, other-person focus, stale evidence, section subject override, XML entity declaration and recovery). These exercised the readers through a temporary local harness, not a prognosis page.
- Production-built file picker: valid JSON, wrong patient reference, malformed JSON, empty file, unsupported extension and recovery behaved as expected. The picker became available again after each check.
- Raw reserved-period files and prepared participant CSVs remain ignored. No final network/privacy audit is claimed; that remains 11.5.

## Check the implementation

From the repository root:

```bash
.venv/bin/python -m pytest -q
cd website
npm ci
npm run typecheck
npm test
npm run lint
npm run build
```

Broad fitting lives in `scripts/cardiovascular_model.py`; inference in `cardiovascular_prognosis.py` never imports training libraries. The saved candidate must not be retuned against the final sample. See the broad model README for reproduction and final-check locking. Synthetic tests run without local NHANES data; data-specific tests skip when files are absent. Browser/Python input fixtures are shared.

## Required before patient prognosis

The broad model improves the earlier experiment's statistical results, but modest five-year improvement does not establish accurate lifetime estimates. Clinical input equivalence, extrapolation, historical-population differences and missing-input selection remain unresolved. Research-mode browser integration remains 11.4. Milestone 11.1–11.3 completion refers to this bounded software prototype, not clinical readiness.
