- Initial cycle: NHANES 2013–2014, mortality follow-up through 2019.
- Population: participants reporting they had previously been told they had congestive heart failure.
- Linked, mortality-eligible sample: **182**.
- Recorded deaths from any cause: **73**.
- Recorded follow-up: **3–85 months**.
- Age recorded as 80 or older: **48 participants**.
- No missing values in the five audited columns.
- Decision: **suitable for exploratory analysis; personalised prognosis feasibility remains unresolved**.

Combined audit: NHANES 2011–2012 and 2013–2014, mortality follow-up through 2019.

- 2011–2012: **187** eligible participants, **95** recorded deaths and **92** without a recorded death; follow-up **2–107 months**.
- 2013–2014: **182** eligible participants, **73** recorded deaths and **109** without a recorded death; follow-up **3–85 months**.
- Combined: **369** eligible participants, **168** recorded deaths and **201** without a recorded death.
- Duplicate participant IDs: **0**.
- Age recorded as 80 or older: **96 participants** across both cycles.
- No missing values in age, sex, follow-up, mortality status or interview weight in either eligible sample.

Use the combined data for exploratory heart-failure survival analysis. Personalised remaining-lifespan estimates and treatment-change estimates remain unsupported. Survey weighting and differences between cycles must be addressed before fitting a model.

Exploratory model comparison (unweighted; survey design and uncertainty not accounted for):

- Fit models using 2011–2012 and check against 2013–2014.
- Age-only Weibull model restricted to ages 40–79: **129** training participants with **55** recorded deaths; **128** checking participants.
- All checking participants have known five-year outcomes: **29** deaths by five years and **99** surviving past five years.
- Average predicted five-year survival: **0.7669834483**; observed proportion: **0.7734375**.
- Age-model five-year Brier score: **0.1780629827**.
- Baseline Weibull model fitted to the same training participants, ignoring age: Brier score **0.1756030707**. Lower scores are better.
- Age-model concordance: **0.5276439259**; 0.5 represents chance-level survival ranking.
- The age-only model's average five-year survival prediction was close to the observed proportion, but individual prediction error did not improve over the baseline. Survival ranking was close to chance. Neither model has established accurate remaining-lifetime estimates.
- The checking cycle has been inspected repeatedly during development; separate data is needed for a final assessment. These point estimates do not establish a statistically reliable difference between models.
- Product implication: do not expose these exploratory lifetime estimates as patient prognosis. Additional clinical inputs, suitable outcome data, assessment of extrapolation beyond follow-up, and uncertainty evaluation remain necessary. Treatment effects and years attributable to individual conditions are not established by these checks.
