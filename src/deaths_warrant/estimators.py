import pandas as pd
from dataclasses import dataclass
from typing import Protocol
from deaths_warrant.km import kaplan_meier
from deaths_warrant.aj import aalen_johansen

@dataclass
class EstimationResult:
    curve: pd.DataFrame
    method: str
    warnings: tuple[str, ...] = ()

class Estimator(Protocol):
    '''.estimate(...) returns EstimationResult(curve, method) with curve containing time and survival while method will either be kaplan_meier or aalen_johansen where AJ would also provide cause CIF columns.'''
    # Specify the shared weighted survival-curve interface for estimator adapters.
    def estimate(self, times, causes, entry = None, weights = None) -> EstimationResult:
        ...

class KaplanMeierEstimator: # Kaplan-Meier Adaptor
    # Convert nonzero causes to deaths and wrap a Kaplan-Meier survival curve.
    def estimate(self, times, causes, entry = None, weights = None) -> EstimationResult:
        events = []
        for cause in causes:
            if cause == 0:
                events.append(0)
            else:
                events.append(1)
        curve = kaplan_meier(times, events, entry = entry, weights = weights)
        return EstimationResult(curve = curve, method = "kaplan_meier")

class AalenJohansenEstimator: # Aalen-Johansen Adaptor
    # Wrap competing-risk survival and cause-incidence curves with their method label.
    def estimate(self, times, causes, entry = None, weights = None) -> EstimationResult:
        curve = aalen_johansen(times, causes, entry = entry, weights = weights)
        return EstimationResult(curve = curve, method = "aalen_johansen")