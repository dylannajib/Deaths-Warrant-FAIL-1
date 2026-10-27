# Cardiovascular record extraction contract (milestone 11.2)

This is a conservative, application-specific interchange subset for the broad cardiovascular model in `cardiovascular_model_plan.md`. It does not interpret arbitrary clinical FHIR or CCD records. Existing HF readers remain available. All fixtures are synthetic.

Milestone 11.4 adds `readFhirCardiovascularEvidence()` and `readCcdCardiovascularEvidence()` for incomplete supported snapshots. They validate all present evidence and document contexts, returning absent fields as missing. The page locks imported values, asks users to supply missing answers, and requires confirmation before `profileFromAnswers()` creates a complete profile. Unsupported units, invalid present values, identity conflicts and ambiguous contexts remain import errors; they do not become a blank form. The original complete-profile reader functions retain their strict contract below.

## Exports and result

- `readFhirCardiovascularProfile(value: unknown, asOf: string): CardiovascularProfile` from `website/src/lib/cardiovascular-fhir-profile.ts`.
- `readCcdCardiovascularProfile(xmlText: string, asOf: string): CardiovascularProfile` from `website/src/lib/cardiovascular-ccda-profile.ts` (requires browser-compatible `DOMParser`).
- Shared `cardiovascular-profile.ts` exports `CardiovascularProfile`, `CardiovascularCode`, `CardiovascularEvidence`, `cardiovascularCodes`, `cardiovascularQuestionSystem`, `cardiovascularQuestionOid`, `readCardiovascularCode`, and `createCardiovascularProfile(evidence, asOf)`. The builder enforces the same complete snapshot rules; readers additionally validate document structure, identity and context.

Successful extraction returns exactly these non-null fields:

```typescript
type CardiovascularProfile = {
  asOf: string; // real YYYY-MM-DD calendar date
  ageYears: number; // integer 40..79, recorded interview age carried into exam
  recordedSex: 1 | 2; // recorded demographic sex: 1=male, 2=female
  heartFailure: boolean;
  coronaryHeartDisease: boolean;
  angina: boolean;
  previousHeartAttack: boolean;
  previousStroke: boolean;
  diabetes: boolean;
  currentSmoker: boolean;
  bmi: number; // positive finite kg/m2
  systolicBloodPressure: number; // positive finite mmHg
  creatinine: number; // positive finite mg/dL
};
```

At least one of the five cardiovascular histories must be true. Missing, refused, unknown, borderline or unsupported answers raise errors. No diagnosis omission becomes false. Both identical and contradictory duplicate evidence raise errors; extraction never selects a latest value or resolves disagreements.

## Exact supported codes

Question system URI: **`urn:deaths-warrant:nhanes-questionnaire:v1`**. Equivalent application-assigned CCD OID: **`2.25.302768291377756359126047998875640721001`**. These identify this local export contract, not an official NHANES terminology service or globally standard clinical codes. Both aliases are accepted by the shared code reader. Exporters must attest the exact question meaning; relabelling general clinical codes is insufficient.

| Exact question code | Meaning | Accepted numeric answers |
| --- | --- | --- |
| `RIDAGEYR` | Completed recorded interview age, carried into exam | Integer 40..79 |
| `RIAGENDR` | Explicit recorded demographic sex corresponding to NHANES RIAGENDR | 1=male, 2=female |
| `MCQ160B` | Ever told had congestive heart failure | 1=yes, 2=no |
| `MCQ160C` | Ever told had coronary heart disease | 1=yes, 2=no |
| `MCQ160D` | Ever told had angina | 1=yes, 2=no |
| `MCQ160E` | Ever told had heart attack | 1=yes, 2=no |
| `MCQ160F` | Ever told had stroke | 1=yes, 2=no |
| `DIQ010` | Told had diabetes | 1=yes, 2=no |
| `SMQ020` | Smoked at least 100 cigarettes during lifetime | 1=yes, 2=no |
| `SMQ040` | Now smoke cigarettes | 1=every day, 2=some days, 3=not at all |

`RIAGENDR` is required as its own numeric observation. Neither FHIR `Patient.gender`, CCD `administrativeGenderCode`, name, nor birth date supplies this answer. The reader does not infer biological sex or gender identity. Likewise, it does not reconstruct interview age from birth date. Optional complete birth dates are validated and cannot be future dates.

`currentSmoker = (SMQ020 === 1 && (SMQ040 === 1 || SMQ040 === 2))`. Both observations are required even for never-100 smokers. Never-100 smokers and former established smokers produce false only from explicit supported answers. A person currently smoking but below 100 lifetime cigarettes is false under this exact definition. General tobacco, vaping, nicotine and generic smoking-status codes are unsupported.

| LOINC code | Snapshot scalar | Exact UCUM unit |
| --- | --- | --- |
| `39156-5` | BMI | `kg/m2` |
| `8480-6` | Systolic blood pressure | `mm[Hg]` |
| `2160-0` | Serum/plasma creatinine | `mg/dL` |

LOINC system URI `http://loinc.org` and OID `2.16.840.1.113883.6.1` are accepted. No unit conversions are implemented: `umol/L`, free-text aliases and approximate/comparator values are rejected. The exporter supplies the exam's scalar SBP (mean of available positive exam readings; a single reading is its own mean); multiple SBP observations/components are unsupported. Creatinine must already be standardised as required by the source model; the reader applies no calibration adjustment.

## Snapshot, identity and context rules

All required observations must be explicitly dated on `asOf`, including the carried-forward interview answers. Their date means **snapshot assessment/attestation date**, not disease onset or original interview date. Exporters must preserve those meanings; importers do not relabel stale measurements. This intentionally rejects more records than the development dataset required. CCD document date must also equal `asOf`. Dates after assessment are rejected everywhere dates are supported. FHIR accepts complete dates or the shared helper's full date-time syntax, comparing the written calendar date (no timezone-to-UTC day reassignment); CCD accepts only `YYYYMMDD`. No arbitrary prior result, period, interval, partial date or repeated reading is selected.

FHIR: a `collection` Bundle with exactly one Patient and only final Observation resources. Entries contain only `resource`; every observation's sole subject reference is exactly `Patient/<id>` with no identifier/contained/absolute/URN alternative. Patient IDs and optional Observation IDs use FHIR's 1..64 letter/digit/dot/hyphen subset. Each observation has exactly one coding and exactly one supported value: unitless `valueInteger` for questions, or `valueQuantity` for measurements with `system: "http://unitsofmeasure.org"`, exact `code` and numeric `value`. Optional quantity `unit` must equal its code. Allowed observation fields are `resourceType`, optional `id`, `subject`, `status`, `code`, `effectiveDateTime` and the relevant value. Patient fields are `resourceType`, `id`, optional `birthDate`, `gender`, and `deceasedBoolean` (only false is accepted when present). Optional `gender` must be a FHIR administrative-gender string (`male`, `female`, `other`, `unknown`); it is ignored for extraction. Unknown fields, Conditions, focus, extensions/modifiers, absent reasons, other statuses/value types, extra codings and unsupported contexts cause errors.

CCD: CDA namespace `urn:hl7-org:v3`, declaring both existing supported US Realm Header/CCD template IDs. Exactly one recordTarget/patientRole/patient with at least one usable identifier is required by the shared identity helpers. Exactly one `component/structuredBody/component/section` is supported. Section code must be `cardiovascular-snapshot` in the local questionnaire OID. Observations must be direct `section/entry/observation` children, `classCode="OBS"`, `moodCode="EVN"`, with one code, completed status, effectiveTime and value. Question values use `xsi:type="INT"`; measurements use `xsi:type="PQ"` and exact UCUM `unit`. Nonnegative plain decimal numeric lexical values only; positive measurement and integer question checks follow. See the fixture for the complete supported tree.

CCD uses an element/attribute allowlist throughout the tree. Subject/participant overrides, related subjects, nested sections/acts/entryRelationships, modifiers, nullFlavor, negation indicators (including explicit false), unrecognised attributes and foreign namespaces are rejected. Narrative is never clinical evidence. Known deceased fields are unsupported and rejected rather than interpreted as living. XML DTD/entity declarations and malformed XML are rejected by the unchanged shared parser. This is an extraction contract, not full FHIR/C-CDA schema or terminology validation; many legitimate clinical exports intentionally fail it.

## Shared synthetic fixtures and verification

`tests/fixtures/cardiovascular/patient-profile.json`, `fhir.json` and `ccd.xml` describe the same synthetic assessment. Frontend tests verify exact parity, each missing field, unknown/out-of-range values, smoking definition, dates, units (including rejection of creatinine `umol/L`), identity, unsupported contexts, XML parser protection and duplicate/conflicting evidence. Existing HF tests continue to run.

Run from `website`: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`. The page now runs the existing Python prediction engine inside a Web Worker; calculations and the frozen model are unchanged. See `milestone_11.md` for browser verification and remaining 11.5 checks.
