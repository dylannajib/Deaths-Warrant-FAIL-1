# Manual cardiovascular record tests

## Follow-up request: real clinical records from 2026

The user selected `tests/fixtures/cardiovascular/manual/real/` for contemporary real records. That entire directory is now Git-ignored. Its local `README.md` records the 28 October 2026 search and source links. No verified, publicly downloadable individual 2026 cardiovascular FHIR or C-CDA records with the requested later outcomes were obtained: **0 of each**, with no new prognosis/outcome comparisons run. The previous historical MIMIC files remain separate and are not labelled contemporary.

The closest 2026 heart-failure source, [RETENTION](https://www.mdpi.com/2073-431X/15/4/212), requires approval for patient-level data. [Registry Forge](https://academic.oup.com/jamiaopen/article/9/5/ooag200/8932407) publishes only synthetic demonstration data; its clinical data cannot be openly shared. [SafeICU](https://safeicu.aiims.edu.in/project/safeicu/) concerns 2015–2025 paediatric CSV records, despite its 2026 publication. A bounded search finding no qualifying files is not evidence that none exist anywhere.

Clinical dates, publication dates, source format and outcome availability must be checked separately. The previous MIMIC import rejection comes from our narrow questionnaire contract and unsupported ordinary FHIR fields, not evidence that FHIR itself is obsolete. Changing the input's year alone does not solve it. Records assessed in 2026 also cannot yet provide multi-year observed follow-up as of October 2026.

Milestone 11.5 is complete for the bounded prototype. These additional tests expose current real-record import limitations; they do not complete general hospital-record support or establish prognosis accuracy. Milestone 12 remains reserved for visual changes.

## Synthetic positive examples

Folder: `tests/fixtures/cardiovascular/manual/fake/`.

- `fhir/`: ten new fictional individual assessments as JSON.
- `ccda/`: the same ten assessments as CCD XML, our supported C-CDA document type.
- `expected-results.json`: exact fictional inputs and frozen-model reference outputs.

Use assessment date **2026-01-01** for every synthetic file. Select a file, review the imported values, confirm and calculate. Compare both formats with the reference. These are application-specific snapshots, not full standards-certified medical exports. Expected outputs test implementation consistency, not clinical truth. All ten format pairs passed the website readers.

## Published real FHIR examples

Local folder: `data/manual-testing/published/mimic-iv-fhir-demo-2.1.0/`.

- `fhir/`: ten selected individual resource excerpts, each from an alive hospital discharge with a later recorded death.
- `README.md`: individual filenames, assessment dates, observed days/years and manual instructions.
- `manual-patients.json`: the ten reference assessments and outcomes, separate from upload files.
- `all-cardiovascular/`: one reference excerpt for each of the 88 cardiovascular participants.
- `cardiovascular-audit.json`: selection rules, per-person follow-up, missing exact questionnaire codes and source hashes.
- `import-results.json`: results from running all 88 excerpts through the current website reader.
- `source/`: original publisher files and licence, retained unchanged.

Companion outcome tables: `data/manual-testing/published/mimic-iv-demo-2.2/source/`. All real participant records and participant-level results stay under ignored `data/`. They are not committed, deployed or placed under public website assets. No model was refitted and no frozen final sample was touched.

The source is [MIMIC-IV Clinical Database Demo on FHIR 2.1.0](https://physionet.org/content/mimic-iv-fhir-demo/2.1.0/), with outcomes from its parent [MIMIC-IV Clinical Database Demo 2.2](https://physionet.org/content/mimic-iv-demo/2.2/). These are openly published de-identified real records. The publisher specifies ODbL 1.0 for the demo files; retain the downloaded licence and attribution if redistributing extracts. The project's own licence does not replace those terms. The full non-demo dataset has different access conditions and was not accessed.

Raw NDJSON resources were grouped into collection Bundles for individual upload testing. The excerpts contain the Patient, index Encounter, diagnoses associated with that admission and selected latest available measurement resources from that encounter, dated no later than the reference discharge date. The original clinical resources are unchanged except that future `Patient.deceasedBoolean`/`deceasedDateTime`, when present, are omitted from alive-assessment views. Originals are retained in `source/`. No living-status answer is invented, no missing questionnaire answer is filled, and no future death date enters the upload file. These are incomplete excerpts; referenced organisations/specimens and other resources can be absent. They are not full FHIR-validation fixtures or native single-patient exports supplied by the publisher.

The 88-person cohort uses ICD-9 390–459 or ICD-10 I00–I99 in any hospital admission. The reference record is the earliest alive discharge associated with one of the model's disease groups where available, otherwise the earliest alive cardiovascular discharge, otherwise the first cardiovascular discharge. This fixed rule chooses one record per participant. For the manual set, choose participants with a supported group and later death, prioritising the model's age range, then source ID. Nine of the ten selected examples are approximately 40–79; the tenth is approximately 89 and is outside model age support. Approximate source age is not a validated replacement for completed questionnaire age.

## What the real-record checks found

| Check | Result |
| --- | ---: |
| Demo participants | 100 |
| Participants with cardiovascular diagnosis codes | 88 |
| Alive at the selected discharge | 83 |
| Recorded later deaths after the selected alive discharge | 25 |
| Observation resources inspected | 782,889 |
| Complete exact application questionnaire snapshots | 0 |
| Current reader imports tested / accepted | 88 / 0 |
| Valid remaining-years predictions / prediction-error comparisons | 0 / 0 |

Every real excerpt currently fails with `Unsupported Patient fields or context.` This is an import-compatibility result, not a prediction that the patient had zero remaining years. Even removing that first structural rejection would not resolve the missing input contract: diagnosis codes do not supply explicit negative histories, and the source's `Tobacco Use History` field does not automatically establish our lifetime-cigarette definition. A separate, justified mapping and missing-input policy would be needed before evaluating the frozen model on this dataset. No average inputs, invented answers or outcome-derived features were used to force predictions.

Observed time is `(recorded death date − alive discharge date) / 365.25`, using calendar days. MIMIC shifts dates for privacy; elapsed time within a patient is retained, while the displayed calendar years are not real historical dates. Missing death dates are unknown/censored. Death linkage is limited beyond one year after the **last** recorded discharge, so an earlier reference discharge can still precede a documented death by several years. See the publisher's [patients documentation](https://mimic.mit.edu/docs/iv/modules/hosp/patients.html).

These are deaths after the assessment, not after publication. Admission billing codes also do not prove the precise time a diagnosis became clinically known. Restricting an accuracy test to people who died would bias the assessment. A model mean is a group expectation, not a promised individual death date; a proper evaluation must also handle patients whose death is not observed.

## Published real C-CDA search

Collected: **zero verified real individual C-CDA records**. Local explanation: `data/manual-testing/published/ccda/README.md`.

Sources checked on 28 October 2026:

- [HL7 C-CDA example](https://cdasearch.hl7.org/examples/view/Documents/History%20and%20Physical): explicitly fictional representative data.
- [ONC certification sample collection](https://github.com/jddamore/ccda-samples): the maintainer explicitly says the patients are fictional, despite documents originating from EHR certification.
- [Synthea](https://synthetichealth.github.io/about.html): fictional records in both formats.
- [HealthEx sample collection](https://docs.healthex.io/api-documentation/patients/testing/sample-patients/): explicitly synthetic, with no real patient data.
- [Clinia sample collection](https://docs.clinia.com/docs/patients/synthetic-patient): explicitly synthetic patient datasets.

No openly downloadable C-CDA source with verified real-individual provenance and suitable reuse terms was established in this search. This does not prove none exists. Neither relabelling fictional examples nor converting the real FHIR excerpts to XML would satisfy the request for published real C-CDA documents, so neither was done.

## Repeat the local checks

With the already downloaded, checksum-verified sources in the local folders:

```bash
.venv/bin/python scripts/audit_mimic_cardiovascular.py
cd website
node scripts/check-mimic-imports.mjs
npm test -- src/lib/manual-cardiovascular-examples.test.ts
```

The Python audit regenerates only its named local excerpts/reports; the ten numbered generated manual FHIR files are replaced. The Node command calls the existing TypeScript reader and records acceptance or its error, without relaxing validation. Neither command trains or changes the model. For another machine, obtain the exact source filenames/checksums listed in the local audit from the two cited public demo releases first.
