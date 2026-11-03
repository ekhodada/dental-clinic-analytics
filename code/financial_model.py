"""Accrual, collection-risk and cash reconciliation in integer CAD cents.

No source amounts are changed. Aging uses service date (not contractual overdue
date). Loss rates are explicit portfolio assumptions, not industry benchmarks.
"""

from pathlib import Path
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import csv
import json
import re

BASE = Path(__file__).resolve().parents[1]


def cents(value):
    """I convert a dollar amount to integer cents."""
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_cents(value):
    """I format integer cents as a two-decimal dollar amount."""
    return format(Decimal(value) / 100, ".2f")


def rows(name):
    """I read one cleaned source table."""
    with (BASE / "processed/clean" / f"{name}.csv").open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(name, data):
    """I save report rows in their existing column order."""
    with (BASE / "processed/reports" / f"{name}.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)


def calculate_invoice_balances(
    invoices, events, location_id, period_start, period_end, cutoff, bands
):
    """I calculate charges, receipts and aged balances for one branch-month."""
    balances = [0] * len(bands)
    receivables = allowance = revenue = received = 0
    for invoice_id, invoice in invoices.items():
        if invoice["loc"] != location_id or invoice["date"] > period_end:
            continue
        paid = sum(amount for when, amount in events[invoice_id] if when <= period_end)
        balance = invoice["bill"] - paid
        assert balance >= 0
        receivables += balance
        age = (cutoff - date.fromisoformat(invoice["date"])).days
        band_index = next(index for index, band in enumerate(bands) if age <= band["max_days"])
        balances[band_index] += balance
        allowance += int(
            (Decimal(balance) * Decimal(str(bands[band_index]["loss_rate"]))).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        if period_start <= invoice["date"] <= period_end:
            revenue += invoice["bill"]
        received += sum(
            amount for when, amount in events[invoice_id] if period_start <= when <= period_end
        )
    return balances, receivables, allowance, revenue, received


def calculate_expense_balances(database, expenses, location_id, period_start, period_end, cutoff):
    """I calculate allocated costs, depreciation, payables and cash payments."""
    allocated = database.execute(
        'SELECT COALESCE(SUM(cents),0) FROM daily_costs WHERE "Location ID"=? AND "Date"'
        " BETWEEN ? AND ?",
        (location_id, period_start, period_end),
    ).fetchone()[0]
    # Depreciation has no payment date and is never a cash outflow.
    depreciation = 0
    payable = 0
    for expense in expenses:
        if expense["Location ID"] != location_id:
            continue
        amount = cents(expense["Amount"])
        cost_start = date.fromisoformat(expense["Cost From"])
        cost_end = date.fromisoformat(expense["Cost To"])
        days = (cost_end - cost_start).days + 1
        covered = max(0, min(days, (cutoff - cost_start).days + 1))
        accrued = (amount // days) * covered + min(amount % days, covered)
        paid_to_date = amount if expense["Paid On"] and expense["Paid On"] <= period_end else 0
        if expense["Cost Type"] == "Depreciation":
            depreciation += database.execute(
                'SELECT COALESCE(SUM(cents),0) FROM daily_costs WHERE "Expense ID"=? AND'
                ' "Date" BETWEEN ? AND ?',
                (expense["Expense ID"], period_start, period_end),
            ).fetchone()[0]
        else:
            payable += accrued - paid_to_date
    cash_paid = sum(
        cents(expense["Amount"])
        for expense in expenses
        if expense["Location ID"] == location_id
        and expense["Paid On"]
        and period_start <= expense["Paid On"] <= period_end
    )
    return allocated, depreciation, payable, cash_paid


def write_weekly_reports(database, provision, monthly):
    """I export main and scenario weekly reports and reconcile their totals."""
    # Main report uses recorded costs. Hypothetical loss provisions stay separate.
    database.execute("DROP VIEW IF EXISTS scenario_weekly_finances")
    database.execute("DROP VIEW IF EXISTS weekly_finances")
    database.execute("DROP VIEW IF EXISTS base_weekly_finances")
    database.execute("DROP TABLE IF EXISTS collection_provisions")
    database.execute(
        'CREATE TABLE collection_provisions (Date TEXT, "Location ID" TEXT, cents INTEGER)'
    )
    database.executemany("INSERT INTO collection_provisions VALUES (?,?,?)", provision)
    sql = (BASE / "code/reports.sql").read_text()
    base_sql = sql[
        sql.index("CREATE VIEW weekly_finances AS") : sql.index("CREATE VIEW patient_trends AS")
    ]
    database.executescript(base_sql)
    database.executescript(
        """CREATE VIEW scenario_weekly_finances AS
    WITH loss AS (SELECT d."Week Starting",p."Location ID",SUM(p.cents) cents
      FROM collection_provisions p JOIN dates d ON p.Date=d.Date GROUP BY 1,2)
    SELECT b."Week Starting",b."Location ID",b."Days Included",b."Week Coverage",
      b."Service Revenue",b."Money Received",
      ROUND(b."Operating Costs"+COALESCE(l.cents,0)/100.0,2) "Operating Costs",
      ROUND(b."Operating Profit"-COALESCE(l.cents,0)/100.0,2) "Operating Profit",
      CASE WHEN b."Service Revenue">0 THEN ROUND((b."Operating Profit"-COALESCE(l.cents,0)/100.0)/b."Service Revenue",6) END "Profit Margin"
    FROM weekly_finances b LEFT JOIN loss l USING("Week Starting","Location ID");"""
    )
    database.commit()
    cursor = database.execute("SELECT * FROM weekly_finances")
    columns = [column[0] for column in cursor.description]
    write("weekly_finances", [dict(zip(columns, row)) for row in cursor.fetchall()])
    cursor = database.execute("SELECT * FROM scenario_weekly_finances")
    columns = [column[0] for column in cursor.description]
    write("scenario_weekly_finances", [dict(zip(columns, row)) for row in cursor.fetchall()])
    actual = sum(cents(row["Operating Profit"]) for row in monthly)
    weekly_total = cents(
        database.execute('SELECT SUM("Operating Profit") FROM weekly_finances').fetchone()[0]
    )
    assert actual == weekly_total
    assert sum(cents(row["Scenario Operating Profit"]) for row in monthly) == cents(
        database.execute(
            'SELECT SUM("Operating Profit") FROM scenario_weekly_finances'
        ).fetchone()[0]
    )


def write_annual_reports(monthly):
    """I aggregate monthly finances and refresh the existing annual financial guide."""
    annual = []
    flow_keys = [
        "Service Revenue",
        "Money Received",
        "Operating Costs",
        "Operating Profit",
        "Scenario Loss Expense",
        "Scenario Operating Profit",
        "Cash Operating Payments",
        "Operating Cash Surplus",
        "Depreciation",
    ]
    for year in sorted({row["Month"][:4] for row in monthly}):
        records = [row for row in monthly if row["Month"].startswith(year)]
        record = {
            "Year": year,
            **{
                column: format(sum(Decimal(row[column]) for row in records), ".2f")
                for column in flow_keys
            },
        }
        last = max(row["Month"] for row in records)
        for column in [
            "Gross Receivables",
            "Scenario Loss Allowance",
            "Scenario Net Receivables",
            "Operating Payables Less Prepayments",
        ]:
            record[column] = format(
                sum(Decimal(row[column]) for row in records if row["Month"] == last), ".2f"
            )
        record["Operating Margin"] = round(
            Decimal(record["Operating Profit"]) / Decimal(record["Service Revenue"]), 6
        )
        record["Scenario Operating Margin"] = round(
            Decimal(record["Scenario Operating Profit"]) / Decimal(record["Service Revenue"]), 6
        )
        annual.append(record)
    write("annual_financials", annual)
    guide = BASE / "FINANCIAL_MODEL.md"
    if guide.exists():
        keys = flow_keys + [
            "Gross Receivables",
            "Scenario Loss Allowance",
            "Scenario Net Receivables",
        ]
        table = (
            "| Measure | "
            + " | ".join(row["Year"] for row in annual)
            + " |\n|---|"
            + "---:|" * len(annual)
            + "\n"
        )
        table += "\n".join(
            "| "
            + column
            + " | "
            + " | ".join("$" + format(Decimal(row[column]), ",.2f") for row in annual)
            + " |"
            for column in keys
        )
        table += (
            "\n| Operating margin | "
            + " | ".join(
                format(Decimal(row["Operating Margin"]) * 100, ".1f") + "%" for row in annual
            )
            + " |"
        )
        table += (
            "\n| Scenario margin | "
            + " | ".join(
                format(Decimal(row["Scenario Operating Margin"]) * 100, ".1f") + "%"
                for row in annual
            )
            + " |"
        )
        text = guide.read_text()
        guide.write_text(
            re.sub(
                r"(?s)<!-- ANNUAL_START -->.*?<!-- ANNUAL_END -->",
                "<!-- ANNUAL_START -->\n" + table + "\n<!-- ANNUAL_END -->",
                text,
            )
        )


def calculate_monthly_reports(database, start, end, bands, invoices, events, expenses, locations):
    """I prepare and reconcile every branch-month on the original financial basis."""
    monthly = []
    aging = []
    provision = []
    checks = []
    previous_balances = {location["Location ID"]: (0, 0, 0) for location in locations}
    period_date = start
    while period_date <= end:
        next_month = (
            date(period_date.year + 1, 1, 1)
            if period_date.month == 12
            else date(period_date.year, period_date.month + 1, 1)
        )
        cutoff = min(end, next_month - timedelta(days=1))
        period_start = period_date.isoformat()
        period_end = cutoff.isoformat()
        for location in locations:
            location_id = location["Location ID"]
            balances, receivables, allowance, revenue, received = calculate_invoice_balances(
                invoices, events, location_id, period_start, period_end, cutoff, bands
            )
            allocated, depreciation, payable, cash_paid = calculate_expense_balances(
                database, expenses, location_id, period_start, period_end, cutoff
            )
            previous_receivables, previous_allowance, previous_payables = previous_balances[
                location_id
            ]
            loss = allowance - previous_allowance
            profit = revenue - allocated
            scenario_profit = profit - loss
            cash = received - cash_paid
            bridge = (
                profit
                + depreciation
                - (receivables - previous_receivables)
                + (payable - previous_payables)
            )
            assert bridge == cash, (period_start, location_id, bridge, cash)
            assert (
                scenario_profit
                + loss
                + depreciation
                - (receivables - previous_receivables)
                + (payable - previous_payables)
                == cash
            )
            assert revenue - received == receivables - previous_receivables
            assert 0 <= allowance <= receivables
            previous_balances[location_id] = (receivables, allowance, payable)
            provision.append([period_end, location_id, loss])
            record = {
                "Month": period_start[:7],
                "Location ID": location_id,
                "Service Revenue": format_cents(revenue),
                "Money Received": format_cents(received),
                "Operating Costs": format_cents(allocated),
                "Operating Profit": format_cents(profit),
                "Operating Margin": round(profit / revenue, 6) if revenue else "",
                "Scenario Loss Expense": format_cents(loss),
                "Scenario Operating Profit": format_cents(scenario_profit),
                "Scenario Operating Margin": (
                    round(scenario_profit / revenue, 6) if revenue else ""
                ),
                "Cash Operating Payments": format_cents(cash_paid),
                "Operating Cash Surplus": format_cents(cash),
                "Gross Receivables": format_cents(receivables),
                "Scenario Loss Allowance": format_cents(allowance),
                "Scenario Net Receivables": format_cents(receivables - allowance),
                "Depreciation": format_cents(depreciation),
                "Operating Payables Less Prepayments": format_cents(payable),
                "Cash Bridge Difference": "0.00",
            }
            monthly.append(record)
            for band_index, band in enumerate(bands):
                aging.append(
                    {
                        "As Of": period_end,
                        "Location ID": location_id,
                        "Invoice Age": band["label"],
                        "Gross Balance": format_cents(balances[band_index]),
                        "Assumed Loss Rate": band["loss_rate"],
                    }
                )
        period_date = next_month
    return monthly, aging, provision


def load_invoice_history():
    """I group service charges and receipt dates separately for each invoice."""
    appointments = {
        appointment["Appointment ID"]: appointment for appointment in rows("appointments")
    }
    invoices = {}
    events = defaultdict(list)
    for treatment in rows("treatments"):
        appointment = appointments[treatment["Appointment ID"]]
        invoice_id = treatment["Invoice ID"]
        invoice = invoices.setdefault(
            invoice_id,
            {
                "date": appointment["Scheduled Start"][:10],
                "loc": appointment["Location ID"],
                "bill": 0,
            },
        )
        invoice["bill"] += cents(treatment["Net Charge"])
    for payment in rows("payments"):
        events[payment["Invoice ID"]].append((payment["Payment Date"], cents(payment["Amount"])))
    return invoices, events


def build():
    """I refresh the reports and their existing validation checks."""
    config = json.loads((BASE / "settings.json").read_text())
    start = date.fromisoformat(config["start_date"])
    end = date.fromisoformat(config["end_date"])
    policy = json.loads((BASE / "financial_policy.json").read_text())
    bands = policy["age_bands"]
    assert [x["max_days"] for x in bands] == sorted({x["max_days"] for x in bands})
    assert all(0 <= x["loss_rate"] <= 1 for x in bands)
    assert bands[-1]["max_days"] >= (end - start).days
    invoices, events = load_invoice_history()
    expenses = rows("expenses")
    locations = rows("locations")
    import sqlite3

    database = sqlite3.connect(BASE / "processed/dental_clinic.sqlite")
    database.execute("PRAGMA temp_store=MEMORY")
    monthly, aging, provision = calculate_monthly_reports(
        database, start, end, bands, invoices, events, expenses, locations
    )
    write_weekly_reports(database, provision, monthly)
    database.close()
    write("monthly_financials", monthly)
    write("receivables_aging", aging)
    write_annual_reports(monthly)
    result = {
        "policy": policy,
        "provisions": provision,
        "checks": {
            "monthly_branch_cash_bridges_reconcile": True,
            "receivables_roll_forward_reconciles": True,
            "scenario_allowances_within_gross_balances": True,
            "main_and_scenario_weekly_monthly_profit_match": True,
            "branch_months_checked": len(monthly),
        },
        "monthly": monthly,
        "aging": aging,
    }
    (BASE / "processed/financial_checks.json").write_text(json.dumps(result["checks"], indent=2))
    return result


if __name__ == "__main__":
    r = build()
    print(json.dumps(r["checks"], indent=2))
