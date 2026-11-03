"""I refresh the Power BI check values and narration from the reporting results."""

from collections import defaultdict
import json
from .clean_and_refresh import BASE
from .check_powerbi import invoice_aging
from .business_questions import money_k


def money(cents):
    """I format an exact validation amount in Canadian dollars."""
    return f"CAD ${cents / 100:,.2f}"


def totals(tables, year, location=None):
    """I calculate annual card values from the exported fact tables."""
    result = {}
    for label, name, day, amount in [
        ("Revenue", "fact_treatments", "ServiceDate", "NetChargeCents"),
        ("Operating Costs", "fact_expenses", "CostDate", "CostCents"),
        ("Cash Collected", "fact_payments", "PaymentDate", "AmountCents"),
    ]:
        result[label] = sum(
            row[amount]
            for row in tables[name]
            if row[day].startswith(str(year))
            and (location is None or row["LocationID"] == location)
        )
    result["Operating Profit"] = result["Revenue"] - result["Operating Costs"]
    result["Operating Margin"] = result["Operating Profit"] / result["Revenue"]
    aging = invoice_aging(tables, f"{year}-12-31", location)
    result["Unpaid Balance by Age"] = sum(aging)
    result["Unpaid Over 90 Days"] = sum(aging[2:])
    result["Unpaid Over 180 Days"] = sum(aging[3:])
    return result


def write_validation(tables):
    """I write exact card, branch, lead-time and waterfall values for Desktop checks."""
    years = sorted({row["Year"] for row in tables["dim_date"]})
    current, previous = years[-1], years[-2]
    results = {year: totals(tables, year) for year in [previous, current]}
    lines = [
        "# My Power BI check values",
        "",
        (
            "I start with all branches and one full year. I compare exact values before rounding"
            " card labels."
        ),
        "",
        f"| Measure | {previous} | {current} |",
        "|---|---:|---:|",
    ]
    for metric in results[current]:
        values = [
            (
                f"{results[year][metric]:.6%}"
                if metric == "Operating Margin"
                else money(results[year][metric])
            )
            for year in [previous, current]
        ]
        lines.append(f"| {metric} | {' | '.join(values)} |")
    change = (results[current]["Revenue"] / results[previous]["Revenue"]) - 1
    lines += [
        f"| Revenue vs Prior Year % | Blank | {change:.6%} |",
        "",
        f"## {current} branch filters",
        "",
        "| Branch | Revenue | Operating profit | Cash collected | Unpaid over 90 days |",
        "|---|---:|---:|---:|---:|",
    ]
    for location in tables["dim_location"]:
        result = totals(tables, current, location["LocationID"])
        values = [
            money(result[key])
            for key in ["Revenue", "Operating Profit", "Cash Collected", "Unpaid Over 90 Days"]
        ]
        lines.append(f"| {location['LocationName']} | {' | '.join(values)} |")
    lead = defaultdict(lambda: [0, 0])
    for row in tables["fact_appointments"]:
        if row["AppointmentDate"].startswith(str(current)):
            lead[row["LeadTimeBand"]][0] += row["Status"] == "No-show"
            lead[row["LeadTimeBand"]][1] += row["Status"] in ["Completed", "No-show"]
    lines += [
        "",
        f"## {current} lead-time chart, all branches",
        "",
        "| Band | No-shows (count) | Completed + missed (count) | Rate |",
        "|---|---:|---:|---:|",
    ]
    for band in ["0-6 days", "7-29 days", "30+ days"]:
        missed, eligible = lead[band]
        lines.append(f"| {band} | {missed:,} | {eligible:,} | {missed / eligible:.6%} |")
    categories = defaultdict(lambda: defaultdict(int))
    for row in tables["fact_treatments"]:
        categories[row["CareCategoryID"]][int(row["ServiceDate"][:4])] += row["NetChargeCents"]
    lines += [
        "",
        "## Revenue waterfall",
        "",
        f"| Care category | {previous} revenue | {current} revenue | Change |",
        "|---|---:|---:|---:|",
    ]
    for category in tables["dim_care_category"]:
        amounts = categories[category["CareCategoryID"]]
        values = [
            money(amounts[previous]),
            money(amounts[current]),
            money(amounts[current] - amounts[previous]),
        ]
        lines.append(f"| {category['CareCategory']} | {' | '.join(values)} |")
    total = results[current]["Revenue"] - results[previous]["Revenue"]
    lines += [
        f"| Total change | | | {money(total)} |",
        "",
        (
            "I check these values in Power BI Desktop after creating the measures; the automated"
            " checks cover exported data and SQL calculations, not a Desktop session."
        ),
    ]
    (BASE / "powerbi/validation.md").write_text("\n".join(lines) + "\n")


def write_walkthrough():
    """I prepare a short recording script using the current findings and policy values."""
    metrics = json.loads((BASE / "processed/business_findings.json").read_text())
    policy = json.loads((BASE / "findings_policy.json").read_text())
    revenue, lead, debt = metrics["revenue"], metrics["lead_time"], metrics["receivables"]
    text = f"""# My recording script

I aim for 1–2 minutes. I start on Summary with {metrics['year']} and all branches selected.

| Time | What I show | What I say |
|---|---|---|
| 0–12 seconds | Headline and cards | “I built this report to explain why operating profit fell\
 {revenue['profit_drop_rate']:.0%} in {metrics['year']}, and which actions deserve attention\
 first. I keep service revenue, cash receipts and unpaid bills separate.” |
| 12–32 seconds | Revenue waterfall; hover Root canal | “Root-canal services fell\
 {revenue['root_service_drop_rate']:.0%}, explaining {revenue['root_revenue_drop_share']:.0%} of\
 the revenue decline. Average charges were broadly steady. I would check referrals, dentist\
 availability and unbooked accepted plans. Recovering half the lost services is\
 {money_k(revenue['opportunity_cents'], 'CAD/year')} in revenue before extra costs.” |
| 32–51 seconds | Lead-time chart; hover 30+ days | “No-shows rise from\
 {lead['bands']['0-6 days']['rate']:.1%} for short-lead bookings to\
 {lead['bands']['30+ days']['rate']:.1%} for long-lead bookings. I would pilot a\
 {policy['reminder_days_before']}-day reminder and a {policy['confirmation_hours_before']}-hour\
 confirmation at Maple. The group opportunity is {money_k(lead['opportunity_cents'], 'CAD/year')}\
 in revenue. I would track no-shows and refilled slots.” |
| 51–69 seconds | Aging chart; hover 91–180 days | “{money_k(debt['over_90_days_cents'])} is\
 unpaid for over 90 days. I would separate insurer, patient and billing-error work. Recovering\
 {policy['collections_recovery_share']:.0%} of the 91-to-180-day balances is\
 {money_k(debt['opportunity_cents'], 'CAD')} in one-off cash. This is not new revenue or extra\
 profit.” |
| 69–96 seconds | Select Maple; drill through from its bar to Appointments; Back; open Patients\
 and Finance | “The branch filter lets me target the pilot. I can inspect booking outcomes,\
 patient activity and financial trends. In Finance, I drill from month to day to investigate\
 changes. I return to Summary and clear the branch filter.” |
| 96–110 seconds | Ranked actions and measurement column | “I rank the actions by estimated\
 value, account for overlapping reminder benefits, and separate one-off collections from\
 recurring revenue. These are opportunities to test, not achieved savings.” |

I record at a readable zoom and pause briefly over tooltips. I rehearse the branch drill-through\
 and date drill-down before recording. I save the recording as `docs/walkthrough-power-bi.mp4`\
 after I build and validate the report.
"""
    (BASE / "powerbi/walkthrough.md").write_text(text)


def build(tables):
    """I refresh the check sheet and narration alongside the Power BI export."""
    write_validation(tables)
    write_walkthrough()
