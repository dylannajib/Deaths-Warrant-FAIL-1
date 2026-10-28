from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
from hashlib import sha256
from pathlib import Path
import csv, gzip, json

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'data/manual-testing/published'
FHIR = FOLDER / 'mimic-iv-fhir-demo-2.1.0'
TABLES = FOLDER / 'mimic-iv-demo-2.2'
QUESTIONS = ['RIDAGEYR', 'RIAGENDR', 'MCQ160B', 'MCQ160C', 'MCQ160D', 'MCQ160E',
    'MCQ160F', 'DIQ010', 'SMQ020', 'SMQ040']
QUESTION_SYSTEMS = ['urn:deaths-warrant:nhanes-questionnaire:v1', '2.25.302768291377756359126047998875640721001']

# Read one official compressed table without changing its source values.
def table(name):
    with gzip.open(TABLES / 'source/hosp' / (name + '.csv.gz'), 'rt') as handle:
        return list(csv.DictReader(handle))

# Stream FHIR resources so the larger observation files are not retained in memory.
def resources(name):
    with gzip.open(FHIR / 'source/fhir' / (name + '.ndjson.gz'), 'rt') as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)

# Verify downloaded payloads against their publisher's manifest before using any records.
def check_sources(folder):
    checksums = dict((line.split()[1].removeprefix('./'), line.split()[0])
        for line in (folder / 'source/SHA256SUMS.txt').read_text().splitlines() if line.strip())
    checked = []
    for file in sorted((folder / 'source').rglob('*')):
        if file.is_file() and file.name != 'SHA256SUMS.txt':
            name = file.relative_to(folder / 'source').as_posix()
            digest = sha256(file.read_bytes()).hexdigest()
            if digest != checksums[name]:
                raise ValueError('Publisher checksum mismatch: ' + name)
            checked.append(dict(file = name, sha256 = digest))
    return checked

# Match the publisher's identifiers instead of inferring identity from names or dates.
def identifier(resource, suffix):
    matches = [item['value'] for item in resource.get('identifier', [])
        if item.get('system') == 'http://mimic.mit.edu/fhir/mimic/identifier/' + suffix]
    if len(matches) != 1:
        raise ValueError('Expected one source identifier')
    return matches[0]

# Select the circulatory-system ICD chapters, including conditions outside our five model histories.
def cardiovascular(row):
    code = row['icd_code'].replace('.', '').upper()
    if row['icd_version'] == '9':
        return len(code) >= 3 and code[:3].isdigit() and 390 <= int(code[:3]) <= 459
    return row['icd_version'] == '10' and len(code) >= 3 and code[0] == 'I' and code[1:3].isdigit()

# Identify the model's supported disease groups without treating missing diagnosis codes as negative answers.
def disease_groups(row):
    code = row['icd_code'].replace('.', '').upper()
    prefix = code[:3]
    if row['icd_version'] == '9':
        return [name for name, present in [('heart failure', prefix == '428'),
            ('coronary heart disease', prefix.isdigit() and 410 <= int(prefix) <= 414),
            ('angina', prefix == '413'), ('heart attack history', prefix in ['410', '412']),
            ('cerebrovascular disease', prefix.isdigit() and 430 <= int(prefix) <= 438)] if present]
    return [name for name, present in [('heart failure', prefix == 'I50'),
        ('coronary heart disease', prefix in ['I20', 'I21', 'I22', 'I23', 'I24', 'I25']),
        ('angina', prefix == 'I20'), ('heart attack history', prefix in ['I21', 'I22'] or code == 'I252'),
        ('cerebrovascular disease', prefix in ['I60', 'I61', 'I62', 'I63', 'I64', 'I65', 'I66', 'I67', 'I68', 'I69'])] if present]

# Save local audit material under the ignored data directory, never under public website assets.
def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent = 2, allow_nan = False) + '\n', encoding = 'utf-8')

# Audit all cardiovascular demo participants and collect ten alive-discharge excerpts with later deaths.
def main():
    checked_sources = {folder.name: check_sources(folder) for folder in [FHIR, TABLES]}
    patients = {row['subject_id']: row for row in table('patients')}
    admissions = {row['hadm_id']: row for row in table('admissions')}
    diagnoses = table('diagnoses_icd')
    cvd = [row for row in diagnoses if cardiovascular(row)]
    by_patient = defaultdict(set)
    by_admission = defaultdict(list)
    for row in cvd:
        by_patient[row['subject_id']].add(row['hadm_id'])
        by_admission[row['hadm_id']].append(row)
    fhir_patients = {identifier(row, 'patient'): row for row in resources('MimicPatient')}
    encounters = {identifier(row, 'encounter-hosp'): row for row in resources('MimicEncounter')}
    conditions = defaultdict(list)
    for row in resources('MimicCondition'):
        conditions[row['encounter']['reference']].append(row)
    output = FHIR / 'all-cardiovascular'
    records = []
    for subject in sorted(by_patient):
        candidate = sorted((admissions[hadm] for hadm in by_patient[subject]), key = lambda row: row['dischtime'])
        person = patients[subject]
        alive = [row for row in candidate if row['hospital_expire_flag'] == '0' and not row['deathtime']
            and (not person['dod'] or row['dischtime'][:10] < person['dod'])]
        supported_alive = [row for row in alive if any(disease_groups(diagnosis) for diagnosis in by_admission[row['hadm_id']])]
        assessment = (supported_alive or alive or candidate)[0]
        hadm = assessment['hadm_id']
        as_of = assessment['dischtime'][:10]
        death = person['dod'] or None
        later_death = bool(alive and death and as_of < death)
        days = (date.fromisoformat(death) - date.fromisoformat(as_of)).days if later_death else None
        age = int(person['anchor_age']) + int(as_of[:4]) - int(person['anchor_year'])
        source_patient = fhir_patients[subject]
        patient = deepcopy(source_patient)
        removed = [key for key in ['deceasedBoolean', 'deceasedDateTime'] if key in patient]
        for key in removed:
            del patient[key]
        encounter = encounters[hadm]
        assert encounter['subject']['reference'] == 'Patient/' + patient['id']
        assert encounter['period']['end'][:10] == as_of
        entries = [patient, encounter, *conditions['Encounter/' + encounter['id']]]
        if not alive:
            entries = [deepcopy(source_patient), encounter, *conditions['Encounter/' + encounter['id']]]
        bundle = dict(resourceType = 'Bundle', type = 'collection', entry = [dict(resource = item) for item in entries])
        filename = 'mimic-' + subject + '.json'
        save(output / filename, bundle)
        records.append(dict(subjectId = subject, hadmId = hadm, file = filename, asOf = as_of,
            aliveAtAssessment = bool(alive), removedFuturePatientFields = removed if alive else [],
            recordedDeathDate = death, deathAfterAssessment = later_death,
            observedDaysAfterAssessment = days, observedYearsAfterAssessment = days / 365.25 if days is not None else None,
            approximateAgeYears = age, ageWithinModelRange = 40 <= age <= 79,
            groups = sorted(set(name for row in by_admission[hadm] for name in disease_groups(row))),
            icd = [dict(version = row['icd_version'], code = row['icd_code']) for row in by_admission[hadm]],
            encounterReference = 'Encounter/' + encounter['id'], patientReference = 'Patient/' + patient['id'],
            modelPrediction = None, predictionStatus = 'Not calculated: source inputs are not validated equivalents of the model questionnaire snapshot.'))
    evidence = defaultdict(set)
    codes = Counter()
    tobacco_codes = set()
    measurement_excerpts = defaultdict(dict)
    assessments = {row['encounterReference']: row for row in records if row['aliveAtAssessment']}
    observation_count = 0
    for name in ['MimicObservationChartevents', 'MimicObservationLabevents', 'MimicObservationVitalSignsED']:
        for row in resources(name):
            observation_count += 1
            for coding in row.get('code', {}).get('coding', []):
                system, code = coding.get('system'), coding.get('code')
                codes[(system, code)] += 1
                if system in QUESTION_SYSTEMS and code in QUESTIONS:
                    evidence[row.get('subject', {}).get('reference')].add(code)
                label = coding.get('display', '').lower()
                if any(word in label for word in ['tobac', 'smok', 'cigarette']):
                    tobacco_codes.add((system, code, coding.get('display', '')))
                assessment = assessments.get(row.get('encounter', {}).get('reference'))
                recorded = row.get('effectiveDateTime', '')
                if assessment and recorded and recorded[:10] <= assessment['asOf'] and any(word in label
                    for word in ['creatinine', 'systolic', 'body mass index', 'height', 'weight']):
                    if row.get('subject', {}).get('reference') != assessment['patientReference']:
                        raise ValueError('Observation subject and encounter disagree')
                    key = (system, code)
                    previous = measurement_excerpts[assessment['subjectId']].get(key)
                    if previous is None or previous.get('effectiveDateTime', '') < recorded:
                        measurement_excerpts[assessment['subjectId']][key] = row
    for row in records:
        row['missingExactQuestionnaireCodes'] = [code for code in QUESTIONS if code not in evidence[row['patientReference']]]
        bundle = json.loads((output / row['file']).read_text())
        bundle['entry'].extend(dict(resource = item) for item in measurement_excerpts[row['subjectId']].values())
        save(output / row['file'], bundle)
        row['measurementExcerptCount'] = len(measurement_excerpts[row['subjectId']])
    later = [row for row in records if row['deathAfterAssessment'] and row['groups']]
    later.sort(key = lambda row: (not row['ageWithinModelRange'], row['subjectId']))
    selected = later[:10]
    manual = FHIR / 'fhir'
    manual.mkdir(parents=True, exist_ok=True)
    for previous in manual.glob('[0-9][0-9]-mimic-*.json'):
        if previous.is_file() and not previous.is_symlink():
            previous.unlink()
    selected_rows = []
    for index, row in enumerate(selected, 1):
        name = f'{index:02d}-mimic-' + row['subjectId'] + '.json'
        bundle = json.loads((output / row['file']).read_text())
        save(manual / name, bundle)
        selected_rows.append(dict(row, file = 'fhir/' + name))
    summary = dict(demoParticipants = len(patients), cardiovascularParticipants = len(records),
        cardiovascularDefinition = 'ICD-9 390-459 or ICD-10 I00-I99 in any hospital admission. Index: earliest alive discharge with a supported disease group where available, otherwise earliest alive cardiovascular discharge, otherwise earliest cardiovascular discharge.',
        aliveAtAssessment = sum(row['aliveAtAssessment'] for row in records),
        knownDeathsAfterAssessment = sum(row['deathAfterAssessment'] for row in records),
        selectedManualPatients = len(selected), observationsScanned = observation_count,
        ageWithinModelRange = sum(row['ageWithinModelRange'] for row in records),
        selectedAgeWithinModelRange = sum(row['ageWithinModelRange'] for row in selected),
        tobaccoCodingLabels = [dict(system = system, code = code, display = label) for system, code, label in sorted(tobacco_codes)],
        exactQuestionnaireObservations = sum(count for (system, code), count in codes.items() if system in QUESTION_SYSTEMS and code in QUESTIONS),
        participantsWithCompleteExactQuestionnaire = sum(not row['missingExactQuestionnaireCodes'] for row in records),
        validModelPredictions = 0, mortalityComparison = 'Not estimable without defensible model inputs; no missing answer was replaced with no or a cohort average.',
        outcomeConvention = 'Calendar days from alive discharge to recorded dod, divided by 365.25. Day precision; shifted dates do not identify real calendar dates.',
        limitations = ['De-identified retrospective source, not deaths observed after public release.',
            'Missing dod is unknown/censored, not proof of survival or immortality.',
            'Deaths are censored beyond one year after the last recorded discharge in the source dataset.',
            'Approximate age from anchor fields is not an exact questionnaire age.',
            'ICD codes establish this audit cohort only; no code is treated as an exact negative questionnaire answer.',
            'Billing diagnoses associated with a stay do not prove the exact time the diagnosis was clinically known.',
            'Selected files are assembled resource excerpts, not complete or fully validated self-contained FHIR exports. Referenced organisations and other resources may be absent.',
            'Selecting only deceased participants cannot measure general prognosis calibration or accuracy.',
            'A fitted mean is not an individual death-date prediction; a single observed lifetime does not establish model accuracy.'])
    report = dict(summary = summary, sourceChecksums = checked_sources, records = records)
    save(FHIR / 'cardiovascular-audit.json', report)
    save(FHIR / 'manual-patients.json', dict(source = 'https://physionet.org/content/mimic-iv-fhir-demo/2.1.0/',
        outcomes = 'https://physionet.org/content/mimic-iv-demo/2.2/', cases = selected_rows))
    print(json.dumps(summary, indent = 2))
    print('Selected observed years:', [(row['subjectId'], round(row['observedYearsAfterAssessment'], 6)) for row in selected])

if __name__ == '__main__':
    main()
