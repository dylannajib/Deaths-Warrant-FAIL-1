import pandas as pd; from deaths_warrant.nhanes import load_demo, load_lmf

def audit_cycle(cycle, medical_path, demo_path, mortality_path):
    print("Cycle:", cycle)
    medical_conditions = pd.read_sas(medical_path, format = "xport")
    print(medical_conditions["MCQ160B"].value_counts(dropna = False))
    medical_conditions = medical_conditions.rename(columns = {"SEQN": "seqn"})
    medical_conditions["seqn"] = medical_conditions["seqn"].astype(int)
    demo = load_demo(demo_path)
    lmf = load_lmf(mortality_path)
    merged = demo.merge(medical_conditions, on = "seqn", how = "inner", validate = "one_to_one")
    merged = lmf.merge(merged, on = "seqn", how = "inner", validate = "one_to_one")
    print(len(merged))
    print(merged["MCQ160B"].value_counts(dropna = False))

    heart_failure = merged[merged["MCQ160B"] == 1]
    print(heart_failure["eligstat"].value_counts(dropna = False))
    eligible_heart_failure = heart_failure[heart_failure["eligstat"] == 1].copy()
    eligible_heart_failure["cycle"] = cycle
    print(eligible_heart_failure["mortstat"].value_counts(dropna = False))
    print(eligible_heart_failure["permth_int"].describe())
    print(eligible_heart_failure[["age_years", "sex", "permth_int", "mortstat", "weight_interview"]].isna().sum())
    print(eligible_heart_failure["age_years"].describe())
    print(eligible_heart_failure["sex"].value_counts(dropna = False))
    print("Age 80 or older:", (eligible_heart_failure["age_years"] == 80).sum())
    print((eligible_heart_failure["permth_int"] <= 0).sum())

    for months in [12, 36, 60]:
        observed_to_horizon = (eligible_heart_failure["permth_int"] >= months).sum()
        print("Months:", months, "Observed to horizon:", observed_to_horizon)
        deaths_by_horizon = ((eligible_heart_failure["mortstat"] == 1) & (eligible_heart_failure["permth_int"] <= months)).sum()
        print("Deaths by horizon:", deaths_by_horizon)

    cardiovascular_questions = {
        "MCQ160C": "Coronary heart disease",
        "MCQ160D": "Angina",
        "MCQ160E": "Heart attack",
        "MCQ160F": "Stroke"
    }

    for column, label in cardiovascular_questions.items():
        print(column)
        print(label)
        print(eligible_heart_failure[column].value_counts(dropna = False))

    for lower, upper in [(20, 39), (40, 59), (60, 79), (80, 80)]:
        age_group = eligible_heart_failure[eligible_heart_failure["age_years"].between(lower, upper)]
        print(lower)
        print(upper)
        print(len(age_group))
        print(age_group["mortstat"].sum())

    return eligible_heart_failure

heart_failure_2013 = audit_cycle(
    "2013-2014", "data/raw/MCQ_H.xpt", "data/raw/DEMO_H.xpt", "data/raw/NHANES_2013_2014_MORT_2019_PUBLIC.dat"
)

heart_failure_2011 = audit_cycle(
    "2011-2012", "data/raw/MCQ_G.xpt", "data/raw/DEMO_G.xpt", "data/raw/NHANES_2011_2012_MORT_2019_PUBLIC.dat"
)

combined = pd.concat([heart_failure_2011, heart_failure_2013], ignore_index = True)

columns = [
    "cycle", "seqn", "age_years", "sex", "MCQ160B", "MCQ160C", "MCQ160D", "MCQ160E", "MCQ160F", "mortstat",
    "permth_int","weight_interview","psu","stratum"
]
combined = combined[columns].copy()

print("Combined participants:", len(combined))
print("Combined mortality:", combined["mortstat"].value_counts(dropna=False))
print("Duplicate participant IDs:", combined["seqn"].duplicated().sum())
print("Participants by cycle:", combined["cycle"].value_counts())