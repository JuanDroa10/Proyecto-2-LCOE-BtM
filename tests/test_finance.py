import pytest

from src import finance


def test_capital_recovery_factor_matches_reference_parameters():
    # i=7.7%, n=20 — the reference model's own values.
    crf = finance.capital_recovery_factor(0.077, 20)
    assert crf == pytest.approx(0.0995890201914585, rel=1e-9)


def test_escalated_capital_recovery_factor_matches_reference_parameters():
    # i=7.7%, n=20, e=2.5% — the reference model's own values.
    crfe = finance.escalated_capital_recovery_factor(0.077, 20, 0.025)
    assert crfe == pytest.approx(0.08275970609929227, rel=1e-9)
