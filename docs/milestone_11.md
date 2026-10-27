# Milestone 11: cardiovascular research prototype

The product goal is a remaining-years estimate from a patient's medical records. The current implementation checkpoint reaches experimental extraction and calculation code; it does not establish a suitable patient-prognosis model.

| Subgoal | Status |
| --- | --- |
| 11.1 — Model/data feasibility | Research routes documented and reproducible candidate evaluated. **Clinical evidence gate remains open:** the current candidate failed its baseline comparison and lifetime accuracy is unestablished. |
| 11.2a — Basic import | Completed checkpoint: supported FHIR JSON and CCD XML structure/identity checks. |
| 11.2b — Clinical-field extraction | Implemented and tested for the explicitly documented research input subset. General clinical interoperability and mapping review remain outstanding. |
| 11.3 — Prognosis calculations | Experimental training, versioned artifact, standard-library inference, model uncertainty and numerical/validation tests implemented. **Patient-prognosis suitability remains blocked by 11.1 evidence.** |
| 11.4 — Browser calculation/results | Pending. Clinical readers and model are not connected to the page. |
| 11.5 — Privacy, performance and builds | Pending final milestone checks. Python/frontend automated checks are in CI; no final browser privacy audit, benchmark or deployment has been performed. |

Milestone 12 remains reserved for user-directed visual polishing.

## Check the implementation

From the repository root:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/audit_heart_failure.py
.venv/bin/python scripts/train_heart_failure.py
cd website
npm ci
npm run typecheck
npm test
npm run lint
npm run build
```

The original audit remains exploratory. The new training command has no import-time fitting and the inference module never imports the training library. Synthetic tests run without local NHANES data; data-specific tests skip when files are absent. The inference tests use exact analytic examples, and simulated censored observations check coefficient recovery. Browser/Python input fixtures are shared.

## Next required decision

Select accessible, permitted clinical data or a suitable published-model route that can support the intended remaining-years output. Do not treat the successful software tests, a plausible mean or the research label as a substitute for that evidence. Completing the software portions of 11.2b and 11.3 does not close this decision.
