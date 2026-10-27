import pytest
from deaths_warrant.estimators import KaplanMeierEstimator, AalenJohansenEstimator
from deaths_warrant.years_lost import integrate_step

@pytest.mark.parametrize("estimator_class", [KaplanMeierEstimator, AalenJohansenEstimator])
# Check both estimator adapters accept weights and delayed entry with matching survival.
def test_estimators_share_interface(estimator_class):
    estimator = estimator_class()
    result = estimator.estimate([2, 4, 5], [1, 2, 0], [0, 0, 3], [2, 1, 3])
    table = result.curve
    assert table["time"].tolist() == [2, 4, 5]
    assert table["survival"].tolist() == pytest.approx([1/3, 1/4, 1/4])

# Ensure the competing-risk adapter retains each cause's incidence and method label.
def test_aj_adaptor_preserves_causes():
    estimator = AalenJohansenEstimator()
    result = estimator.estimate([2, 4, 5], [1, 2, 0], [0, 0, 3], [2, 1, 3])
    table = result.curve
    assert table["cif_1"].tolist() == pytest.approx([2/3, 2/3, 2/3])
    assert table["cif_2"].tolist() == pytest.approx([0, 1/12, 1/12])
    assert result.method == "aalen_johansen"

@pytest.mark.parametrize("estimator_class", [KaplanMeierEstimator, AalenJohansenEstimator])
# Ensure either estimator's survival curve can feed the same restricted-years integration.
def test_estimators_share_years_workflow(estimator_class):
    estimator = estimator_class()
    result = estimator.estimate([1, 2, 2, 3, 4], [1, 2, 0, 1, 0])
    table = result.curve
    curve_times = table["time"].tolist()
    survival_values = table["survival"].tolist()
    integrate = integrate_step(curve_times, survival_values, 0, 4, 1)
    assert integrate == pytest.approx(2.7)