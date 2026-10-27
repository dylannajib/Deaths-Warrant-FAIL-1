# Experimental heart-failure inputs

This is a supported subset for research, not general FHIR/C-CDA validation or a clinical prognosis specification. The website still uses its existing structural importer; connecting these clinical readers is Milestone 11.4.

## Intended product and current boundary

The product goal remains an estimate of remaining years from patient medical records. Updating that estimate after changes in disease or treatment, and explaining contributions of individual conditions, remain separate evidence requirements. The current model does not establish those capabilities.

The implemented candidate uses NHANES 2011–2012 self-reported heart-failure history, age, previous heart attack and previous stroke. It is checked against 2013–2014. It deliberately excludes ages below 40 and the top-coded 80+ category. Clinical records are not identical to survey self-reports; applying this model to those records is unvalidated.

No clinical release is authorised by these results. The candidate failed to improve five-year Brier error over a baseline ignoring patient characteristics. Research inference requires `research_mode=True`; normal calls refuse to run.

## Shared profile

Both readers return the same keys, with unknown values represented by `null`. The Python inference engine independently requires the same fields and rejects unknown or additional fields.

| Field | Meaning | Required for calculation |
| --- | --- | --- |
| `asOf` | Explicit assessment calendar date, `YYYY-MM-DD` | Valid complete date |
| `ageYears` | Completed years on that date | Integer 40–79 |
| `heartFailure` | Documented history, not current severity | Explicit `true` |
| `previousHeartAttack` | Personal history of myocardial infarction | Explicit boolean |
| `previousStroke` | Personal history of stroke | Explicit boolean |

This candidate has no laboratory measurements, units to convert, sex/gender mapping or treatment inputs. It does not infer any of them. Their absence limits suitability; it is not evidence that they are unimportant.

Birth dates must be complete and valid. Calendar dates use the date written in the record, not a conversion to the browser's timezone. Evidence after `asOf` is rejected. The reader does not infer that an old negative history remains current: callers must choose a clinically appropriate assessment date and provide records for that assessment. Freshness and clinical reconciliation are not established by successful parsing.

Absence of a diagnosis is never a negative history. Contradictory supported assertions raise an error rather than selecting a convenient answer. Refuted diagnoses do not prove the person has never had the condition. A resolved confirmed event can still establish a positive history.

## Recognised codes

Only the following explicit SNOMED CT codes are recognised. There is no terminology server, descendant expansion, ICD translation or matching by display text. SNOMED coding system is `http://snomed.info/sct` in FHIR and OID `2.16.840.1.113883.6.96` in CDA.

| Code | Use |
| --- | --- |
| `84114007`, `42343007` | Heart failure / congestive heart failure history |
| `22298006`, `1755008`, `399211009` | Myocardial infarction / old myocardial infarction / history of myocardial infarction |
| `230690007`, `275526006` | Stroke / history of stroke |

Explicit negative histories are recognised only for the history-specific codes `399211009` and `275526006`. Negating a current stroke or myocardial infarction does not establish that no event ever occurred. This small registry is a prototype mapping and needs clinical/terminology review before wider use.

## FHIR JSON adaptor

`website/src/lib/fhir-profile.ts`: `readFhirProfile(value, asOf)`.

- Reuses the existing one-Patient Bundle and relative `Patient/id` reference checks. Other resources and reference forms remain unsupported.
- Uses `Patient.birthDate`. Deceased patients and unsupported modifier extensions are rejected.
- Recognised Conditions need confirmed verification and a recognised clinical status. Provisional, refuted and entered-in-error entries do not establish history.
- Conditions need a usable `recordedDate` or `onsetDateTime`. A provided onset date is also checked against the assessment date.
- Alternative Condition onset forms and Observation focus contexts are rejected rather than assumed to describe this patient's history at the assessment date.
- Explicit history Observations need `final`, `amended` or `corrected` status, `valueBoolean`, and `effectiveDateTime`. Missing answers stay unknown.
- Only complete date strings or the documented full date-time form with timezone are accepted. Partial dates are not guessed.

The valid fictional example is `tests/fixtures/fhir/heart-failure-profile.json`. Its history Observations demonstrate the supported representation, not a claim that every provider export includes it.

## CCD XML adaptor

`website/src/lib/ccda-profile.ts`: `readCcdProfile(xmlText, asOf)`.

- Reuses existing CDA namespace, declared header/CCD template roots and single-patient identifier checks. This is not full schema or template-version validation.
- Reads a complete `patient/birthTime` date.
- Reads coded Problem Observations (`2.16.840.1.113883.10.20.22.4.4`) only inside a declared Problems section (`...22.2.5` or `...22.2.5.1`) under the structured body.
- Requires `OBS`/`EVN`, completed status, an ASSERTION code and a coded `CD` value. Narrative text, family-history sections and unknown values do not become patient diagnoses.
- Reads the observation's effective date or low boundary. Supports complete `YYYYMMDD` dates and the implemented full timestamp forms; rejects partial dates.
- Recognises `negationInd` only for explicit history assertions. Subject overrides (including at section level) and negated/unknown enclosing acts are rejected.
- Rejects document-type/entity declarations. It does not retrieve external terminology or records.

The fictional XML example is a focused importer fixture, not a fully conformant clinical CCD. All contents are invented. It produces exactly the same profile as the FHIR example and `tests/fixtures/prognosis/patient-profile.json`.

## Evidence and access decisions

- [NHANES 2011–2012 questionnaire](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2011/DataFiles/MCQ_G.htm) and [2013–2014 questionnaire](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2013/DataFiles/MCQ_H.htm): usable local research foundation; `MCQ160B/E/F` are historical self-reports, not severity or treatment response.
- [MAGGIC study](https://pubmed.ncbi.nlm.nih.gov/23095984/): established mortality-risk work with clinically relevant inputs. Complete implementation/redistribution permissions and a suitable remaining-lifetime method are not established here.
- [Seattle Heart Failure Model](https://depts.washington.edu/shfm/update.php): includes mean life-expectancy output. Its [website terms](https://depts.washington.edu/shfm/EULA.php) limit that site's use to knowledgeable healthcare providers; they do not establish permission to distribute our own patient-facing implementation.
- [HF-ACTION](https://biolincc.nhlbi.nih.gov/studies/hf_action/): a more clinically detailed potential source, but a selected historical trial population and not unrestricted downloadable data. [BioLINCC access](https://biolincc.nhlbi.nih.gov/faq/) requires an application, ethics documentation and an agreement; the study also has consent restrictions. No application has been submitted or access assumed.
- [FHIR Condition absence guidance](https://hl7.org/fhir/R4/condition.html): checklist-style negative histories need explicit observation/questionnaire assertions, not an assumption based on missing Conditions.

## Remaining evidence work

Obtain appropriate clinical input/outcome evidence and permitted access; choose a candidate before inspecting new checking results; reserve separate data for final assessment; evaluate uncertainty, patient groups, source differences and longer-term extrapolation. Assess treatment updates and condition attribution separately. A research label does not establish clinical suitability.
