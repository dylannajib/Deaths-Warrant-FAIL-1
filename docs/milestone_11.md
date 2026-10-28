# Milestone 11: cardiovascular research prototype

The product goal is a remaining-years estimate from a patient's medical records. The current implementation checkpoint reaches experimental extraction and calculation code; it does not establish a suitable patient-prognosis model.

| Subgoal | Status |
| --- | --- |
| 11.1 — Model/data feasibility | **Research-prototype assessment complete.** Broad candidate frozen, weighting sensitivity recorded and reserved 2009–2010 check completed. Five-year error modestly improves over both baselines; three-year error does not. Lifetime accuracy and patient-prognosis suitability remain unestablished. See `models/cardiovascular/README.md`. |
| 11.2a — Basic import | Completed checkpoint: supported FHIR JSON and CCD XML structure/identity checks. |
| 11.2b — Clinical-field extraction | **Prototype subset complete.** Strict broad FHIR/CCD questionnaire snapshot readers return the same complete profile; ordinary EHR exports are not generally supported. See `cardiovascular_record_contract.md`. Existing HF readers are retained. |
| 11.3 — Prognosis calculations | **Research engine complete.** Versioned broad artifact, standard-library inference, fitted-mean bootstrap interval, support checks and parity tests implemented. Research acknowledgement remains required; no treatment or individual-condition attribution is claimed. |
| 11.4 — Browser calculation/results | **Prototype integration complete.** Supported snapshots prefill locked imported values; users complete missing fields and confirm the assessment. A Web Worker runs the existing Python engine through Pyodide and displays mean remaining years, fitted-mean uncertainty and survival checks. Retry, timeout, clear and stale-result handling are implemented. |
| 11.5 — Privacy, performance and builds | **Complete for the research prototype.** Approved build published at https://deaths-warrant.pages.dev/. Public file integrity, HTTPS/security headers, caching/compression, synthetic calculations and mobile viewport/emulation checks passed. Physical-phone testing and clinical suitability are not established. See the public verification reports and `deployment.md`. |

Milestone 12 remains reserved for user-directed visual polishing.

## Public release verification — 28 October 2026

- Production URL: https://deaths-warrant.pages.dev/. Deployment: `34dcc7a4`. Release: `92e83cdeb406d4c6b0683db5ad403a41da005e5c253b6a135cf62f492a945d04`. This publishes the approved static artifact, without Functions, a patient database or an upload endpoint.
- All 53 checked served files matched the release. HTTPS security headers, exact CSP, immutable/revalidation rules, WebAssembly MIME/gzip, ETag 304 and secured 404 passed. HTTP returned 301 to HTTPS. See `public-host-verification.json`.
- Desktop collaborative-browser FHIR and CCD imports each displayed 17.4 mean years. Clear removed the form/result.
- A separate Chromium test used a real 375-by-667 viewport after the collaborative preview twice retained 1280-by-800 despite resize requests. FHIR/CCD parity, missing creatinine, range rejection/recovery, malformed XML/recovery and Clear passed. Initial and result views had no horizontal overflow. See `public-browser-verification.json`.
- The mobile-sized test applied fourfold CPU slowdown and page-network settings of 200,000 bytes/s download and 150 ms latency. Startup took 33.81 s. Page-level network emulation may not throttle every worker transfer. This is desktop emulation, not a physical-phone or universal startup-time claim.
- Request capture included workers: all startup/Clear requests fetched same-origin software using GET. Import and calculation issued no requests. Local/session storage and IndexedDB were empty; no unexpected JavaScript errors occurred.
- One bounded batch of 100 concurrent public model-file requests returned 100 HTTP 200 responses in 6.28 s. This checks static delivery from this connection, not 100 browser sessions or guaranteed capacity. See `public-performance-results.json`.
- Physical mobile-device/browser coverage remains follow-up work. The frozen model, its inspected final sample and the clinical limitations are unchanged.

## Release preparation verification — 28 October 2026

- Python: 206 passed. Frontend: 170 passed. TypeScript, lint, static build and release checks passed, including a clean installation in a disposable copy with no previous build cache.
- Cloudflare local Pages runtime served the exact checked files with the expected CSP, security/cache headers, WebAssembly MIME type, gzip bodies, ETag 304 and 404 behaviour. `host-verification.json` records the tested local release.
- The real browser blocked unapproved inline JavaScript and an external connection. The existing frozen Python model still calculated the same synthetic output. Complete FHIR/CCD, missing inputs, range error/recovery, malformed XML and Clear checks passed under that policy.
- Fresh browser worker readiness: 4.96 s locally. One hundred sequential calculations: 5.52 ms mean, 7.90 ms p95. One hundred concurrent static model requests all returned 200. These are local desktop measurements, not mobile/public capacity tests.
- Build-time source runtime checks are repeated against exported runtime bytes during release validation. Regression tests reject missing or modified runtime files even if release metadata is regenerated. The prognosis model was not refitted or changed.
- CI retains the checked public static artifact for review and does not auto-deploy. No hosting account, paid service, commit, push or public deployment was created by this preparation task.
- Public HTTPS redirects, HSTS over HTTPS, edge compression/cache behaviour and mobile observations must be checked after an approved deployment. Instructions and rollback steps are in `deployment.md`.

## Browser integration verification — 27 October 2026

- Python: 206 tests passed. Frontend: 153 tests passed; TypeScript, lint and static production build passed.
- Real production browser with Pyodide: the shared synthetic FHIR and CCD records both returned 17.4 displayed mean years, matching local Python's 17.435570518699695. The displayed fitted-mean interval was 13.4–23.3; survival checks were 98.9%, 94.3% and 88.0% at 1/3/5 years.
- Removing cigarette-exposure and creatinine observations left exactly those controls blank and editable. Completing them reproduced the original result. Imported values stayed locked.
- Editing a manual answer removed the old result and confirmation. Creatinine 999 produced a readable training-range error; restoring 1.1 allowed calculation again.
- Wrong patient references and malformed JSON cleared the prior form/result and displayed errors. A subsequent valid CCD import succeeded.
- Clear removed the form, result and file reference and replaced the worker. No secure-erasure claim is made.
- Unit tests cover worker request IDs, malformed responses, cancellation, startup/calculation deadlines and temporary-global cleanup. A final network/privacy audit and performance benchmark remain 11.5.
- `predev` and `prebuild` copy only the frozen model and standard-library inference source into ignored `website/public/prognosis/`; no fitting libraries or participant records are shipped.

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

The broad model improves the earlier experiment's statistical results, but modest five-year improvement does not establish accurate lifetime estimates. Clinical input equivalence, extrapolation, historical-population differences and missing-input selection remain unresolved. Milestone 11.1–11.4 completion refers to this bounded software prototype, not clinical readiness.
