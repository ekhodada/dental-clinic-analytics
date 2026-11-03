"""I test failure detection, financial identities and analysis results."""

import json
import csv
import subprocess
import sys
from decimal import Decimal
from dental_analytics import validation
from dental_analytics.clean_and_refresh import BASE
from dental_analytics.check_analyses import main as check_analyses
from dental_analytics.check_findings import main as check_findings
from dental_analytics.check_refresh import main as check_refresh


def test_overlapping_booking_is_rejected(checked_data):
    """I prove that conflicting reservations fail the resource overlap rules."""
    changed = dict(checked_data)
    changed["appointments"] = dict(checked_data["appointments"])
    row = dict(next(iter(changed["appointments"].values())))
    row["Appointment ID"] = "CONFLICT"
    changed["appointments"]["CONFLICT"] = row
    assert not validation.check_provider_overlap(changed)
    assert not validation.check_chair_overlap(changed)
    assert not validation.check_patient_overlap(changed)


def test_wrong_charge_is_rejected(checked_data):
    """I prove that an incorrect net charge fails reconciliation."""
    changed = dict(checked_data)
    changed["tables"] = dict(checked_data["tables"])
    rows = list(changed["tables"]["treatments"])
    rows[0] = dict(rows[0], **{"Net Charge": "0.01"})
    changed["tables"]["treatments"] = rows
    assert not validation.check_charge_math(changed)


def test_duplicate_payment_is_rejected(checked_data):
    """I prove that repeated receipt identifiers fail uniqueness."""
    changed = dict(checked_data)
    changed["tables"] = dict(checked_data["tables"])
    rows = changed["tables"]["payments"]
    changed["tables"]["payments"] = rows + [rows[0]]
    assert not validation.check_unique_payments(changed)


def test_profit_reconciles_to_cash():
    """I independently recompute every branch-month profit-to-cash identity."""
    with (BASE / "processed/reports/monthly_financials.csv").open() as stream:
        months = list(csv.DictReader(stream))
    previous = {}
    assert len(months) == 72
    for row in months:
        branch = row["Location ID"]
        unpaid = Decimal(row["Gross Receivables"])
        payables = Decimal(row["Operating Payables Less Prepayments"])
        old_unpaid, old_payables = previous.get(branch, (Decimal(0), Decimal(0)))
        profit = Decimal(row["Operating Profit"])
        assert profit == Decimal(row["Service Revenue"]) - Decimal(row["Operating Costs"])
        cash = Decimal(row["Money Received"]) - Decimal(row["Cash Operating Payments"])
        bridge = profit + Decimal(row["Depreciation"]) - (unpaid - old_unpaid)
        bridge += payables - old_payables
        assert bridge == cash == Decimal(row["Operating Cash Surplus"])
        previous[branch] = unpaid, payables


def test_package_runs_from_another_folder(tmp_path):
    """I verify installed imports and module commands from outside the repository."""
    result = subprocess.run(
        [sys.executable, "-m", "dental_analytics.clean_and_refresh", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--input" in result.stdout
    subprocess.run(
        [sys.executable, "-c", "import dental_analytics.build_dashboard_data"],
        cwd=tmp_path,
        check=True,
    )


def test_analysis_results_and_boundaries():
    """I verify analyses and date and denominator boundaries."""
    check_analyses()


def test_findings_and_recommendations():
    """I verify findings and overlapping recommendation values."""
    check_findings()


def test_repeatability_and_failed_publication(tmp_path):
    """I prove repeated inputs match and invalid inputs preserve prior output."""
    check_refresh(tmp_path)
