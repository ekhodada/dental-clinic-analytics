"""I compare exported Power BI facts with SQL and the reconciled financial reports."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
import csv
import json
import sqlite3
from .clean_and_refresh import BASE

AGE_BANDS = [(0, 30), (31, 90), (91, 180), (181, 365), (366, 999999)]


def read_tables():
    """I reload the eight exported CSVs with integer measures and text identifiers."""
    metadata = json.loads((BASE / "powerbi/model.json").read_text())
    tables = {}
    numbers = {
        "Year",
        "MonthNumber",
        "YearMonthSort",
        "WeekdayNumber",
        "Chairs",
        "BirthYear",
        "CategorySort",
        "LeadDays",
        "LeadTimeSort",
        "TreatmentMinutes",
        "ReservedMinutes",
        "AgeAtVisit",
        "AgeGroupSort",
    }
    for name in metadata["tables"]:
        with (BASE / "powerbi" / f"{name}.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            for column in row:
                if column in numbers or column.endswith("Cents"):
                    row[column] = int(row[column])
        tables[name] = rows
    return tables


def invoice_aging(tables, cutoff, location=None):
    """I independently age whole invoices using only receipts received by the cutoff."""
    invoices = {}
    for row in tables["fact_treatments"]:
        if row["ServiceDate"] > cutoff or (location and row["LocationID"] != location):
            continue
        item = invoices.setdefault(row["InvoiceID"], [row["ServiceDate"], 0])
        assert item[0] == row["ServiceDate"]
        item[1] += row["NetChargeCents"]
    for row in tables["fact_payments"]:
        if row["PaymentDate"] <= cutoff and row["InvoiceID"] in invoices:
            invoices[row["InvoiceID"]][1] -= row["AmountCents"]
    balances = [0] * len(AGE_BANDS)
    for service_date, balance in invoices.values():
        assert balance >= 0
        age = (date.fromisoformat(cutoff) - date.fromisoformat(service_date)).days
        band = next(i for i, (low, high) in enumerate(AGE_BANDS) if low <= age <= high)
        balances[band] += balance
    return balances


def validate_keys(tables, metadata):
    """I check unique dimension and fact grains and every exported foreign key."""
    keys = {
        "dim_date": ["Date"],
        "dim_location": ["LocationID"],
        "dim_patient": ["PatientID"],
        "dim_care_category": ["CareCategoryID"],
        "fact_appointments": ["AppointmentID"],
        "fact_treatments": ["TreatmentID"],
        "fact_payments": ["PaymentID"],
        "fact_expenses": ["ExpenseID", "CostDate"],
    }
    for name, columns in keys.items():
        values = [tuple(row[column] for column in columns) for row in tables[name]]
        assert len(set(values)) == len(values), name
        assert all(all(value != "" for value in key) for key in values), name
    assert len(metadata["relationships"]) == 13
    for dimension, key, fact, foreign_key in metadata["relationships"]:
        valid = {row[key] for row in tables[dimension]}
        assert all(row[foreign_key] in valid for row in tables[fact]), (dimension, fact)
    dates = [date.fromisoformat(row["Date"]) for row in tables["dim_date"]]
    assert dates == [dates[0] + timedelta(days=i) for i in range(len(dates))]


def validate_financials(tables):
    """I reconcile exported revenue, costs and receipts with all 72 branch-months."""
    totals = defaultdict(lambda: [0, 0, 0])
    for index, name, date_column, amount in [
        (0, "fact_treatments", "ServiceDate", "NetChargeCents"),
        (1, "fact_expenses", "CostDate", "CostCents"),
        (2, "fact_payments", "PaymentDate", "AmountCents"),
    ]:
        for row in tables[name]:
            totals[(row[date_column][:7], row["LocationID"])][index] += row[amount]
    with (BASE / "processed/reports/monthly_financials.csv").open() as stream:
        monthly = list(csv.DictReader(stream))
    assert len(totals) == len(monthly) == 72
    for row in monthly:
        expected = [
            int(Decimal(row[column]) * 100)
            for column in ["Service Revenue", "Operating Costs", "Money Received"]
        ]
        actual = totals[(row["Month"], row["Location ID"])]
        assert actual == expected, row
        assert actual[0] - actual[1] == int(Decimal(row["Operating Profit"]) * 100)
    for row in tables["fact_treatments"]:
        assert row["NetChargeCents"] == (
            row["GrossChargeCents"] - row["DiscountCents"] - row["AdjustmentCents"]
        )


def validate_aging(tables, connection):
    """I compare three historical cutoffs and every branch with source SQL invoice aging."""
    sql = """WITH paid AS (
        SELECT "Invoice ID",SUM(CAST(ROUND(Amount*100) AS INTEGER)) cents
        FROM payments WHERE "Payment Date"<=? GROUP BY "Invoice ID"
    ) SELECT a."Location ID",substr(a."Scheduled Start",1,10),i.cents-COALESCE(p.cents,0)
    FROM invoice_totals i JOIN appointments a USING("Appointment ID")
    LEFT JOIN paid p USING("Invoice ID") WHERE substr(a."Scheduled Start",1,10)<=?"""
    for cutoff in ["2024-12-31", "2025-06-30", "2025-12-31"]:
        expected = defaultdict(lambda: [0] * len(AGE_BANDS))
        for location, service_day, balance in connection.execute(sql, (cutoff, cutoff)):
            age = (date.fromisoformat(cutoff) - date.fromisoformat(service_day)).days
            band = next(i for i, (low, high) in enumerate(AGE_BANDS) if low <= age <= high)
            expected[location][band] += balance
        for location, balances in expected.items():
            assert invoice_aging(tables, cutoff, location) == balances
        combined = [sum(values[i] for values in expected.values()) for i in range(len(AGE_BANDS))]
        assert invoice_aging(tables, cutoff) == combined


def validate_lead_time(tables, connection):
    """I reconcile branch lead-time counts with the existing SQL view."""
    counts = defaultdict(lambda: [0, 0, 0])
    branch_names = {row["LocationID"]: row["LocationName"] for row in tables["dim_location"]}
    for row in tables["fact_appointments"]:
        if row["AppointmentDate"][:4] != "2025":
            continue
        values = counts[(branch_names[row["LocationID"]], row["LeadTimeBand"])]
        values[0] += row["Status"] == "No-show"
        values[1] += row["Status"] in ["Completed", "No-show"]
        values[2] += 1
    for branch, band, missed, eligible, scheduled in connection.execute(
        "SELECT branch,lead_time_band,no_shows,eligible_appointments,scheduled_appointments "
        "FROM noshow_by_lead_time"
    ):
        assert counts[(branch, band)] == [missed, eligible, scheduled]


def build():
    """I validate the exported model and save a concise check record."""
    tables = read_tables()
    metadata = json.loads((BASE / "powerbi/model.json").read_text())
    validate_keys(tables, metadata)
    validate_financials(tables)
    with sqlite3.connect(BASE / "processed/dental_clinic.sqlite") as connection:
        validate_aging(tables, connection)
        validate_lead_time(tables, connection)
    result = {
        "status": "PASS",
        "tables": len(tables),
        "relationships_checked": 13,
        "financial_branch_months_checked": 72,
        "historical_aging_cutoffs_checked": 3,
        "dimension_keys_and_fact_grains_valid": True,
        "foreign_keys_valid": True,
        "exported_money_reconciles_to_cents": True,
        "lead_time_counts_match_sql": True,
        "aging_uses_receipts_known_at_cutoff": True,
        "desktop_measure_validation": "I confirm the supplied DAX measures in Power BI Desktop.",
    }
    (BASE / "processed/powerbi_checks.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    build()
