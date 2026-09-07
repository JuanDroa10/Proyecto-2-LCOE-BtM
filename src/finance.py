"""Capital-recovery-factor helpers shared by the dispatch model and LCOE calculator.

Mirrors the reference model's own annuity math: a single representative
year's cash flow is annuitized over the project life to get an NPV, using
crf (no cost escalation) or crfe (with escalation) as the annuity factor.
"""


def capital_recovery_factor(i: float, n: int) -> float:
    """Standard capital recovery factor: i(1+i)^n / ((1+i)^n - 1)."""
    return (i * (1 + i) ** n) / ((1 + i) ** n - 1)


def escalated_capital_recovery_factor(i: float, n: int, e: float) -> float:
    """Capital recovery factor adjusted for a constant annual cost escalation e."""
    ir = (i - e) / (1 + e)
    return (1 + e) * (ir * (1 + ir) ** n) / ((1 + ir) ** n - 1)
