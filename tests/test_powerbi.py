"""I verify the Power BI exports without requiring a Desktop installation."""

from datetime import date, timedelta
import json
import re
import sqlite3
import pytest
from dental_analytics.clean_and_refresh import BASE
from dental_analytics.check_powerbi import (
    invoice_aging,
    read_tables,
    validate_aging,
    validate_financials,
    validate_keys,
    validate_lead_time,
)


@pytest.fixture(scope="module")
def powerbi_tables():
    """I load the published model once for the export tests."""
    return read_tables()


def test_powerbi_keys_and_grains(powerbi_tables):
    """I verify all dimension keys, fact grains and thirteen relationship keys."""
    metadata = json.loads((BASE / "powerbi/model.json").read_text())
    validate_keys(powerbi_tables, metadata)


def test_powerbi_money_matches_reconciled_branch_months(powerbi_tables):
    """I reconcile exported money and charge arithmetic to the cent."""
    validate_financials(powerbi_tables)


def test_powerbi_aging_matches_historical_sql(powerbi_tables):
    """I verify past year-end and mid-year aging against the source database."""
    with sqlite3.connect(BASE / "processed/dental_clinic.sqlite") as connection:
        validate_aging(powerbi_tables, connection)


def test_powerbi_no_show_lead_time_matches_sql(powerbi_tables):
    """I verify branch and lead-time numerator and denominator counts."""
    with sqlite3.connect(BASE / "processed/dental_clinic.sqlite") as connection:
        validate_lead_time(powerbi_tables, connection)


def test_powerbi_aging_boundaries_and_future_receipts():
    """I test exact age boundaries, multi-line invoices and late receipt exclusion."""
    cutoff = date(2025, 12, 31)
    tables = {"fact_treatments": [], "fact_payments": []}
    for age in [30, 31, 90, 91, 180, 181, 365, 366]:
        invoice = str(age)
        day = (cutoff - timedelta(days=age)).isoformat()
        for amount in [600, 400]:
            tables["fact_treatments"].append(
                {
                    "InvoiceID": invoice,
                    "ServiceDate": day,
                    "LocationID": "L1",
                    "NetChargeCents": amount,
                }
            )
        for payment_day, amount in [(day, 200), ("2026-01-01", 300)]:
            tables["fact_payments"].append(
                {"InvoiceID": invoice, "PaymentDate": payment_day, "AmountCents": amount}
            )
    assert invoice_aging(tables, cutoff.isoformat()) == [800, 1600, 1600, 1600, 800]


def test_powerbi_wrong_cost_fails_reconciliation(powerbi_tables):
    """I prove that a one-cent expense error fails the export checks."""
    changed = dict(powerbi_tables)
    rows = list(changed["fact_expenses"])
    rows[0] = dict(rows[0], CostCents=rows[0]["CostCents"] + 1)
    changed["fact_expenses"] = rows
    with pytest.raises(AssertionError):
        validate_financials(changed)


def test_powerbi_unknown_dimension_key_fails(powerbi_tables):
    """I prove that an unknown branch identifier fails relationship validation."""
    changed = dict(powerbi_tables)
    rows = list(changed["fact_payments"])
    rows[0] = dict(rows[0], LocationID="UNKNOWN")
    changed["fact_payments"] = rows
    metadata = json.loads((BASE / "powerbi/model.json").read_text())
    with pytest.raises(AssertionError):
        validate_keys(changed, metadata)


def test_powerbi_guide_links_and_measure_inventory():
    """I check local guide links and the nine requested named measure definitions."""
    for filename in ["README.md", "validation.md", "walkthrough.md"]:
        path = BASE / "powerbi" / filename
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text()):
            if not target.startswith(("https://", "#")):
                assert (path.parent / target.split("#")[0]).exists(), target
    measures = (BASE / "powerbi/measures.dax").read_text()
    for name in [
        "Revenue",
        "Operating Costs",
        "Operating Profit",
        "Operating Margin",
        "Cash Collected",
        "Unpaid Over 90 Days",
        "No-show Rate",
        "No-show Rate by Lead Time",
        "Revenue vs Prior Year %",
    ]:
        assert f"\n{name} =\n" in measures
    assert "TREATAS" in measures and "REMOVEFILTERS ( dim_date )" in measures
