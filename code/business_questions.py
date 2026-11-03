"""Refresh three business answers directly from the checked reporting database."""

from pathlib import Path
import sqlite3
import json

BASE = Path(__file__).resolve().parents[1]


def explain_revenue_change(database, total_decline):
    """I explain the revenue decline using service counts and average charges."""
    cursor = database.execute("SELECT * FROM revenue_change_by_care")
    columns = [column[0] for column in cursor.description]
    categories = [dict(zip(columns, row)) for row in cursor.fetchall()]
    assert round(sum(row["Revenue Change"] for row in categories), 2) == round(-total_decline, 2)
    for row in categories:
        assert (
            abs(row["Service Count Effect"] + row["Average Charge Effect"] - row["Revenue Change"])
            <= 0.011
        )
    largest = min(categories, key=lambda row: row["Revenue Change"])
    previous_year = largest["Previous Year"]
    current_year = largest["Current Year"]
    header = (
        f"| Care category | {previous_year} services | {current_year} services | Revenue change"
        " (CAD) |\n|---|---:|---:|---:|"
    )
    table_rows = []
    for row in categories:
        change = row["Revenue Change"]
        amount = f"{'-' if change < 0 else '+'}${abs(change):,.0f}"
        table_rows.append(
            f"| {row['Care Category']} | {row['Previous Services']:,} | "
            f"{row['Current Services']:,} | {amount} |"
        )
    service_drop = largest["Previous Services"] - largest["Current Services"]
    service_drop_rate = service_drop / largest["Previous Services"]
    decline_share = -largest["Revenue Change"] / total_decline
    charge_change = largest["Current Average Charge"] / largest["Previous Average Charge"] - 1
    summary = (
        f"{largest['Care Category']} explains **{decline_share:.1%} of the net revenue decline**. "
        f"Its service count fell by **{service_drop:,} ({service_drop_rate:.1%})**, "
        f"while its average net charge changed by only **{charge_change:+.1%}** "
        f"(CAD ${largest['Previous Average Charge']:,.0f} to "
        f"CAD ${largest['Current Average Charge']:,.0f} per service). "
        "The category's decline therefore comes mainly from fewer completed services."
    )
    return "\n\n".join(
        [
            "### Which care contributed most to the revenue decline?",
            header + "\n" + "\n".join(table_rows),
            summary,
            (
                "**Next investigation:** Check referrals sent elsewhere, dentist availability and"
                " accepted treatment plans that were not booked. These are explanations to"
                " investigate; the existing data does not establish why the service count fell."
            ),
            (
                "**Measure next:** Monthly completed services in this category, referral-out"
                " counts and accepted plans converted to bookings. The last two measures require"
                " additional records."
            ),
            (
                "[Detailed service-count and average-charge calculations]"
                "(processed/reports/revenue_change_by_care.csv)."
            ),
        ]
    )


def build():
    """I refresh the reports and their existing validation checks."""
    database = sqlite3.connect(BASE / "processed/dental_clinic.sqlite")
    database.execute("PRAGMA temp_store=MEMORY")
    current_year = database.execute("SELECT MAX(substr(Date,1,4)) FROM dates").fetchone()[0]
    previous_year = str(int(current_year) - 1)
    care = database.execute(
        """SELECT t."Care Category",COUNT(DISTINCT a."Patient ID"),COUNT(*),
        SUM(CAST(ROUND(t."Net Charge"*100) AS INTEGER))/100.0
        FROM treatments t JOIN appointments a USING("Appointment ID")
        WHERE substr(a."Scheduled Start",1,4)=? GROUP BY 1 ORDER BY 3 DESC""",
        (current_year,),
    ).fetchall()
    activity = database.execute(
        """SELECT substr("Scheduled Start",1,4),COUNT(*),
        SUM(Status='Completed'),SUM(Status='No-show'),SUM(Status='Cancelled')
        FROM appointments GROUP BY 1 ORDER BY 1"""
    ).fetchall()
    branches = database.execute(
        '''SELECT l."Location Name",COUNT(*),SUM(a.Status='Completed'),
        SUM(a.Status='No-show'),SUM(a.Status='Cancelled') FROM appointments a
        JOIN locations l USING("Location ID") WHERE substr(a."Scheduled Start",1,4)=?
        GROUP BY l."Location ID"''',
        (current_year,),
    ).fetchall()
    capacity = database.execute(
        """SELECT SUM("Treatment Minutes"),SUM("Available Minutes")
        FROM capacity WHERE substr(Month,1,4)=?""",
        (current_year,),
    ).fetchone()
    # Calendar-year totals use monthly reports, rather than assigning boundary weeks to one year.
    import csv

    with (BASE / "processed/reports/annual_financials.csv").open() as f:
        years = list(csv.DictReader(f))
    current_activity = next(x for x in activity if x[0] == current_year)
    previous_finances = next(x for x in years if x["Year"] == previous_year)
    current_finances = next(x for x in years if x["Year"] == current_year)
    patient_count = database.execute(
        """SELECT COUNT(DISTINCT "Patient ID") FROM appointments
        WHERE Status='Completed' AND substr("Scheduled Start",1,4)=?""",
        (current_year,),
    ).fetchone()[0]
    overdue = database.execute(
        'SELECT SUM("Overdue Patients") FROM recall_trends WHERE Month=?', (current_year + "-12",)
    ).fetchone()[0]
    revenue_drop = float(previous_finances["Service Revenue"]) - float(
        current_finances["Service Revenue"]
    )
    cost_drop = float(previous_finances["Operating Costs"]) - float(
        current_finances["Operating Costs"]
    )
    profit_drop = float(previous_finances["Operating Profit"]) - float(
        current_finances["Operating Profit"]
    )
    assert round(revenue_drop - cost_drop, 2) == round(profit_drop, 2)
    care_total = sum(x[2] for x in care)
    routine = next(x for x in care if x[0] == "Routine & Preventive Care")
    data = {
        "year": current_year,
        "patients": patient_count,
        "care_categories": care,
        "activity": activity,
        "branch_activity": branches,
        "treatment_minutes": capacity[0],
        "available_minutes": capacity[1],
        "overdue_recall_patients": overdue,
        "financial_years": years,
        "profit_bridge_difference": round(revenue_drop - cost_drop - profit_drop, 2),
    }
    (BASE / "processed/business_findings.json").write_text(json.dumps(data, indent=2))
    branch_table = "\n".join(
        f"| {name} | {miss/(complete+miss):.1%} | {cancel/bookings:.1%} |"
        for name, bookings, complete, miss, cancel in branches
    )
    revenue_investigation = explain_revenue_change(database, revenue_drop)
    text = f"""# Three business questions and answers

Reporting period: {current_year}, all three branches. Comparisons use the full previous year. These are findings within a synthetic case study, not results from a real client.

## 1. Which services do our patients use most?

**Dashboard:** Patient Overview.

**Answer:** Routine and preventive care accounts for **{routine[2]:,} of {care_total:,} completed services ({routine[2]/care_total:.1%})**, used by **{routine[1]:,} of {patient_count:,} patients ({routine[1]/patient_count:.1%})**. It generates **${routine[3]:,.0f}** in service revenue.

**Recommendation:** Protect hygiene and check-up availability. Review demand and waiting times before changing appointment blocks. Service volume alone does not establish treatment profitability or clinical need.

**Measure next:** Recall bookings completed, waiting time and clinical utilization. Do not increase treatments purely to raise revenue.

![Patient Overview](docs/images/07-patient-overview.png)

## 2. Where should we investigate missed visits and unused capacity?

**Dashboard:** Key Trends.

**Answer:** Of **{current_activity[1]:,} bookings**, **{current_activity[2]:,} were completed**, **{current_activity[3]:,} were missed**, and **{current_activity[4]:,} were cancelled**. The missed-visit rate is **{current_activity[3]/(current_activity[2]+current_activity[3]):.1%}** of completed plus missed bookings. Direct care uses **{capacity[0]/capacity[1]:.1%}** of available dentist and hygienist time.

| Branch | Missed / completed + missed | Cancelled / all bookings |
|---|---:|---:|
{branch_table}

**Recommendation:** Investigate Maple's missed visits and Meadow's cancellations first. Review booking lead time and cancellation reasons. Pilot reminders and a consent-based short-notice waitlist; compare with similar appointment groups that did not receive the reminder before claiming an improvement.

**Measure next:** Missed-visit rate, cancellation rate, cancelled slots refilled and actual care utilization. Non-treatment time also includes preparation and other useful work; it is not automatically wasted time.

There are **{overdue:,} overdue recall patients** at year-end. Review their latest plans and future bookings before contacting them. This is not a churn count.

![Key Trends](docs/images/08-key-trends.png)

## 3. Why did operating profit fall, and is cash also positive?

**Dashboard:** Treatment & Costs.

**Answer:** Service revenue fell by **${revenue_drop:,.0f}**, while recorded operating costs fell by only **${cost_drop:,.0f}**. The difference explains the **${profit_drop:,.0f}** fall in operating profit. Rent and several staff cost categories are unchanged in the model, so costs do not fall as quickly as revenue.

| Measure | {previous_year} | {current_year} |
|---|---:|---:|
| Service revenue | ${float(previous_finances['Service Revenue']):,.0f} | ${float(current_finances['Service Revenue']):,.0f} |
| Operating costs | ${float(previous_finances['Operating Costs']):,.0f} | ${float(current_finances['Operating Costs']):,.0f} |
| Operating profit, before estimated collection losses | ${float(previous_finances['Operating Profit']):,.0f} | ${float(current_finances['Operating Profit']):,.0f} |
| Operating margin, same basis | {float(previous_finances['Operating Margin']):.1%} | {float(current_finances['Operating Margin']):.1%} |
| Operating cash surplus | ${float(previous_finances['Operating Cash Surplus']):,.0f} | ${float(current_finances['Operating Cash Surplus']):,.0f} |

{revenue_investigation}

**Recommendation:** Review weekly branch revenue and controllable costs together. Investigate unfilled appointment slots and older unpaid bills before adding marketing spend. Profit is positive on the stated basis, but collections still need attention.

**Measure next:** Weekly profit and margin, actual operating cash surplus, and unpaid bills by age. The optional collection-risk scenario is separate from recorded results and is not evidence of actual losses.

![Treatment & Costs](docs/images/09-treatment-costs.png)

## What this project demonstrates

Business questions → clear data definitions → repeatable cleaning → checked reports → interactive dashboards → findings → actions → measures for follow-up.

No intervention has been run. Recommendations are proposed actions, not claimed revenue gains or achieved cost savings. The fixed synthetic patient pool causes late-period new-patient counts to fall; that pattern must not be interpreted as a real marketing or seasonal effect.
"""
    (BASE / "BUSINESS_QUESTIONS.md").write_text(text)
    database.close()
    return data


if __name__ == "__main__":
    build()
