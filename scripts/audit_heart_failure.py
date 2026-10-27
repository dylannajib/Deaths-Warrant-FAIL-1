import pandas as pd; from deaths_warrant.nhanes import load_demo, load_lmf
from math import exp, gamma
from lifelines import WeibullFitter, WeibullAFTFitter
from lifelines.utils import concordance_index
from deaths_warrant.km import kaplan_meier
from deaths_warrant.years_lost import summarise_years

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

follow_up_years = (combined["permth_int"]/12).tolist()
deaths = combined["mortstat"].astype(int).tolist()
curve = kaplan_meier(follow_up_years, deaths)
summary = summarise_years(curve, 0, 5)
print(summary)

total_follow_up_years = (combined["permth_int"].sum()) / 12
recorded_deaths = (combined["mortstat"] == 1).sum()
exponential_mean_years = total_follow_up_years/recorded_deaths
print(total_follow_up_years)
print(recorded_deaths)
print(exponential_mean_years)

exponential_survival_5 = exp(-5 / exponential_mean_years)
print("Exponential five-year-survival:", exponential_survival_5)

weibull = WeibullFitter()
weibull.fit(follow_up_years, event_observed=deaths)
shape = weibull.rho_
scale = weibull.lambda_
print("Weibull Shape:", shape)
print("Weibull Scale:", scale)
weibull_mean_years = scale * gamma(1 + 1 / shape)
weibull_survival_5 = exp(-((5/scale) ** shape))
print("Weibull mean remaining years:", weibull_mean_years)
print("Weibull five-year survival:", weibull_survival_5)

training = heart_failure_2011
checking = heart_failure_2013
training_years = (training["permth_int"]/12).tolist()
training_deaths = (training["mortstat"]).astype(int).tolist()
training_exponential_mean = (training["permth_int"].sum() / 12) / (training["mortstat"] == 1).sum()
training_weibull = WeibullFitter()
training_weibull.fit(training_years, event_observed=training_deaths)
checking_years = (checking["permth_int"] / 12).tolist()
checking_deaths = checking["mortstat"].astype(int).tolist()
checking_curve = kaplan_meier(checking_years, checking_deaths)

for year in [1, 3, 5]:
    observed = checking_curve[checking_curve["time"] <= year].iloc[-1]["survival"]
    exponential_prediction = exp(-year / training_exponential_mean)
    weibull_prediction = exp(-((year/training_weibull.lambda_) ** training_weibull.rho_))
    print("Year:", year)
    print("Observed:", observed)
    print("Exponential:", exponential_prediction)
    print("Weibull:", weibull_prediction)

age_training = training[training["age_years"].between(40, 79)].copy()
age_training["follow_up_years"] = age_training["permth_int"] / 12
age_model = WeibullAFTFitter()
age_model.fit(age_training, duration_col = "follow_up_years", event_col = "mortstat", formula = "age_years")
examples = pd.DataFrame({"age_years": [40, 60, 75]})
examples["estimated_years"] = age_model.predict_expectation(examples)
print(examples)

age_checking = checking[checking["age_years"].between(40, 79)].copy()
early_censored = ((age_checking["mortstat"] == 0) & (age_checking["permth_int"] < 60)).sum()
print("Observation ended before five years:", early_censored)
if early_censored > 0:
    raise ValueError("Five-year outcome checks require complete five-year outcomes; some observations ended early.")

predicted_survival_5 = age_model.predict_survival_function(age_checking, times = [5]).iloc[0]
print("Average predicted survival:", predicted_survival_5.mean())

died_by_5 = ((age_checking["mortstat"] == 1) & (age_checking["permth_int"] <= 60))
observed_survival_5 = 1 - died_by_5.mean()
print("Observed survival:", observed_survival_5)

actual_survival_5 = 1 - died_by_5.astype(int)
age_brier = ((predicted_survival_5 - actual_survival_5) ** 2).mean()
print("Age model five-year error:", age_brier)

baseline_model = WeibullFitter()
baseline_model.fit(age_training["follow_up_years"], event_observed=age_training["mortstat"])
baseline_survival_5 = baseline_model.survival_function_at_times([5]).iloc[0]
baseline_brier = ((baseline_survival_5 - actual_survival_5) ** 2).mean()
print("Baseline five-year error:", baseline_brier)

predicted_medians = age_model.predict_median(age_checking)
age_concordance = concordance_index(age_checking["permth_int"] / 12, predicted_medians, age_checking["mortstat"])
print("Age model survival ranking:", age_concordance)
