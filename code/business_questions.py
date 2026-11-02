"""I generate four findings and their calculation evidence from the reporting database."""
from pathlib import Path
import json
import sqlite3
from analysis_stats import branch_noshow_test

BASE = Path(__file__).resolve().parents[1]
PARTS = ["What happened", "Why", "What it's worth", "What to do", "How to measure"]


# I read named query results so each calculation uses clear field names.
def query_rows(connection, query, parameters=()):
    cursor = connection.execute(query, parameters)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# I calculate annual revenue, costs and cash directly from dated ledger records.
def annual_totals(connection, year):
    dates = (f"{year}-01-01", f"{year}-12-31")
    revenue = query_rows(connection, '''
        SELECT COALESCE(SUM(i.cents),0) revenue_cents,COUNT(*) completed_visits
        FROM invoice_totals i JOIN appointments a USING("Appointment ID")
        WHERE a.Status='Completed' AND substr(a."Scheduled Start",1,10) BETWEEN ? AND ?
    ''', dates)[0]
    costs = query_rows(connection, '''
        SELECT e."Cost Type" cost_type,SUM(d.cents) cost_cents
        FROM daily_costs d JOIN expenses e USING("Expense ID")
        WHERE d.Date BETWEEN ? AND ? GROUP BY e."Cost Type"
    ''', dates)
    paid = connection.execute('''
        SELECT COALESCE(SUM(CAST(ROUND(Amount*100) AS INTEGER)),0)
        FROM expenses WHERE "Paid On" BETWEEN ? AND ? AND "Cost Type"<>'Depreciation'
    ''', dates).fetchone()[0]
    return {**revenue, "year": year,
            "costs_by_type": {row["cost_type"]: row["cost_cents"] for row in costs},
            "cost_cents": sum(row["cost_cents"] for row in costs),
            "cash_paid_cents": paid}


# I calculate positive invoice balances using only receipts known at the cutoff.
def invoice_ages(connection, cutoff):
    return query_rows(connection, '''
        WITH paid AS (
            SELECT "Invoice ID",SUM(CAST(ROUND(Amount*100) AS INTEGER)) cents
            FROM payments WHERE "Payment Date"<=? GROUP BY "Invoice ID"
        )
        SELECT i."Invoice ID" invoice_id,i.cents-COALESCE(p.cents,0) unpaid_cents,
            CAST(julianday(?)-julianday(substr(a."Scheduled Start",1,10)) AS INTEGER) age_days
        FROM invoice_totals i JOIN appointments a USING("Appointment ID")
        LEFT JOIN paid p USING("Invoice ID")
        WHERE substr(a."Scheduled Start",1,10)<=? AND i.cents>COALESCE(p.cents,0)
    ''', (cutoff, cutoff, cutoff))


# I group booking outcomes by branch and lead-time band without averaging percentages.
def booking_totals(connection):
    rows = query_rows(connection, "SELECT * FROM noshow_by_lead_time")
    bands = {}
    branches = {}
    for row in rows:
        band = row["lead_time_band"]
        totals = bands.setdefault(band, {"no_shows": 0, "eligible_appointments": 0})
        totals["no_shows"] += row["no_shows"]
        totals["eligible_appointments"] += row["eligible_appointments"]
        branches.setdefault(row["branch"], {})[band] = row["no_show_rate"]
    for totals in bands.values():
        totals["rate"] = totals["no_shows"] / totals["eligible_appointments"]
    return bands, branches


# I value the four findings using observed quantities and separate planning inputs.
def calculate_metrics(connection, policy):
    year = int(connection.execute("SELECT MAX(substr(Date,1,4)) FROM dates").fetchone()[0])
    cutoff = connection.execute("SELECT MAX(Date) FROM dates").fetchone()[0]
    previous = annual_totals(connection, year - 1)
    current = annual_totals(connection, year)
    bridge = query_rows(connection, "SELECT * FROM revenue_bridge")
    root = next(row for row in bridge if row["care_category"] == "Root Canal & Pulp Care")
    root_lost = root["services_2024"] - root["services_2025"]
    root_average_cents = round(root["net_revenue_2025_cad"] * 100) / root["services_2025"]
    revenue_drop = previous["revenue_cents"] - current["revenue_cents"]
    profit_before = previous["revenue_cents"] - previous["cost_cents"]
    profit_now = current["revenue_cents"] - current["cost_cents"]
    unchanged_costs = sum(amount for category, amount in current["costs_by_type"].items()
                          if previous["costs_by_type"].get(category) == amount)
    fixed_categories = ["Rent", "Hygienist wages", "Assistant wages", "Reception wages", "Manager wages"]
    rent_and_salary_unchanged = all(previous["costs_by_type"].get(name) ==
                                    current["costs_by_type"].get(name) for name in fixed_categories)
    bands, branches = booking_totals(connection)
    short, middle, long = (bands[name] for name in ["0-6 days", "7-29 days", "30+ days"])
    average_visit_cents = current["revenue_cents"] / current["completed_visits"]
    retained_visits = max(0, long["no_shows"] - middle["rate"] * long["eligible_appointments"])
    pattern_count = sum(rates["30+ days"] > rates["7-29 days"] > rates["0-6 days"]
                        for rates in branches.values())
    balances = invoice_ages(connection, cutoff)
    age_balance = lambda low, high: sum(row["unpaid_cents"] for row in balances
                                       if low <= row["age_days"] <= high)
    oldest_age = max(row["age_days"] for row in balances)
    comparison = branch_noshow_test(connection)
    maple, harbour = comparison["groups"]["Maple"], comparison["groups"]["Harbour"]
    maple_visits = max(0, (maple["no_show_rate"] - harbour["no_show_rate"]) * maple["eligible_appointments"])
    maple_revenue = connection.execute('''
        SELECT SUM(i.cents) FROM invoice_totals i JOIN appointments a USING("Appointment ID")
        JOIN locations l USING("Location ID")
        WHERE l."Location Name"='Maple' AND substr(a."Scheduled Start",1,4)=?
    ''', (str(year),)).fetchone()[0]
    maple_completed = maple["eligible_appointments"] - maple["no_shows"]
    return {
        "year": year, "previous_year": year - 1, "cutoff": cutoff,
        "revenue": {
            "revenue_drop_cents": revenue_drop,
            "revenue_drop_rate": revenue_drop / previous["revenue_cents"],
            "profit_drop_rate": (profit_before - profit_now) / profit_before,
            "root_lost_services": root_lost,
            "root_service_drop_rate": root_lost / root["services_2024"],
            "root_revenue_drop_share": -round(root["revenue_change_cad"] * 100) / revenue_drop,
            "root_average_charge_cents": root_average_cents,
            "root_recovered_services": root_lost * policy["root_canal_recovery_share"],
            "opportunity_cents": round(root_lost * policy["root_canal_recovery_share"] * root_average_cents),
            "average_charge_effect_cents": round(sum(row["price_effect_cad"] for row in bridge) * 100),
            "unchanged_cost_share": unchanged_costs / current["cost_cents"],
            "rent_and_salary_unchanged": rent_and_salary_unchanged,
        },
        "lead_time": {
            "bands": bands, "branch_count": len(branches), "pattern_branch_count": pattern_count,
            "rate_multiple": long["rate"] / short["rate"],
            "retained_visits": retained_visits, "average_visit_cents": average_visit_cents,
            "opportunity_cents": round(retained_visits * average_visit_cents),
        },
        "receivables": {
            "total_unpaid_cents": sum(row["unpaid_cents"] for row in balances),
            "over_90_days_cents": age_balance(91, oldest_age),
            "collections_balance_cents": age_balance(policy["collections_min_age_days"],
                                                       policy["collections_max_age_days"]),
            "recovery_base_cents": age_balance(91, 180),
            "opportunity_cents": round(age_balance(91, 180) * policy["collections_recovery_share"]),
            "previous_year_cash_timing_lift_cents": previous["cost_cents"] -
                previous["costs_by_type"].get("Depreciation", 0) - previous["cash_paid_cents"],
        },
        "branch_gap": {
            "retained_visits": maple_visits,
            "average_maple_visit_cents": maple_revenue / maple_completed,
            "opportunity_cents": round(maple_visits * maple_revenue / maple_completed),
            "higher_in_every_lead_band": all(branches["Maple"][band] > branches["Harbour"][band]
                                             for band in bands),
            "overlaps_group_reminder_opportunity": True,
        },
        "noshow_comparison_2025": comparison,
    }


# I label each dollar figure as estimated and round headline amounts to thousands.
def money_k(cents, unit="CAD"):
    return f"estimated ~${cents / 100000:,.0f}K {unit}"


# I write each finding with the same five short, first-person parts.
def make_findings(metrics, policy):
    revenue = metrics["revenue"]
    lead = metrics["lead_time"]
    debt = metrics["receivables"]
    gap = metrics["branch_gap"]
    test = metrics["noshow_comparison_2025"]
    maple, harbour = test["groups"]["Maple"], test["groups"]["Harbour"]
    significance = ("statistically significant" if test["p_value"] < policy["significance_threshold"]
                    else "not statistically significant")
    p_description = (f'p < {policy["significance_threshold"]:g}'
                     if test["p_value"] < policy["significance_threshold"]
                     else f'p = {test["p_value"]:.6f}')
    fixed_cost_explanation = (
        "I find rent and salaried staff costs unchanged, so costs fell more slowly than revenue."
        if revenue["rent_and_salary_unchanged"] else
        "I compare rent and salaried staff costs with revenue to investigate the faster profit decline."
    )
    branch_explanation = (
        "I also find Maple above Harbour within every booking lead-time band, so I would investigate its confirmation workflow."
        if gap["higher_in_every_lead_band"] else
        "I would check how booking lead-time mix contributes to the difference between branches."
    )
    return [
        {"title": "Recover lost root-canal visits", "parts": dict(zip(PARTS, [
            f'I find revenue fell {money_k(revenue["revenue_drop_cents"])} '
            f'({revenue["revenue_drop_rate"]:.1%}) and operating profit fell '
            f'{revenue["profit_drop_rate"]:.0%} from {metrics["previous_year"]} to {metrics["year"]}.',
            f'I find broadly steady average charges; {revenue["root_revenue_drop_share"]:.0%} of the revenue decline '
            f'came from {revenue["root_service_drop_rate"]:.0%} fewer root-canal services, averaging '
            f'estimated ${revenue["root_average_charge_cents"] / 100:,.0f} CAD/service. {fixed_cost_explanation}',
            f'I estimate recovering {revenue["root_recovered_services"]:.0f} of the '
            f'{revenue["root_lost_services"]:,} lost services ({policy["root_canal_recovery_share"]:.0%}) '
            f'could add {money_k(revenue["opportunity_cents"], "CAD/year")} in service revenue, before extra costs.',
            'I would check referrals sent elsewhere, dentist availability and accepted-but-unbooked treatment plans.',
            'I would track root-canal services per month and the treatment-plan acceptance rate.',
        ]))},
        {"title": "Confirm long-lead bookings", "parts": dict(zip(PARTS, [
            f'I find the no-show rate is {lead["bands"]["30+ days"]["rate"]:.1%} for 30+-day bookings versus '
            f'{lead["bands"]["0-6 days"]["rate"]:.1%} for bookings under 7 days, about '
            f'{lead["rate_multiple"]:.1f} times as high.',
            f'I find the same rising pattern in {lead["pattern_branch_count"]} of '
            f'{lead["branch_count"]} branches, so I would test whether reminders and confirmations improve attendance.',
            f'I estimate matching the 7–29-day rate could retain about {lead["retained_visits"]:.0f} visits/year '
            f'and add {money_k(lead["opportunity_cents"], "CAD/year")} in service revenue, before extra costs.',
            f'I would pilot a reminder {policy["reminder_days_before"]} days before care and a reply-to-confirm '
            f'{policy["confirmation_hours_before"]} hours before care at one branch. '
            'I would have staff review unconfirmed slots before offering them to a short-notice waitlist.',
            'I would track the no-show rate for 30+-day bookings and slots refilled against a comparison branch.',
        ]))},
        {"title": "Collect older unpaid bills", "parts": dict(zip(PARTS, [
            f'I find {money_k(debt["over_90_days_cents"])} of {money_k(debt["total_unpaid_cents"])} '
            f'owed is over 90 days old at {metrics["cutoff"]}.',
            'I would check whether insurer delays, patient balances or billing errors explain the older bills. '
            f'I note an {money_k(debt["previous_year_cash_timing_lift_cents"])} timing lift in '
            f'{metrics["previous_year"]} cash because tracked unpaid operating bills start at zero.',
            f'I estimate recovering {policy["collections_recovery_share"]:.0%} of 91–180-day bills could release '
            f'{money_k(debt["opportunity_cents"])} in cash, before collection costs. '
            'I would not count this as new service revenue or subtract unpaid bills from profit.',
            f'I would run a collections process for {policy["collections_min_age_days"]}–'
            f'{policy["collections_max_age_days"]}-day bills ({money_k(debt["collections_balance_cents"])}), '
            'classifying each balance as insurer, patient or billing-error work.',
            'I would track days to collect and the unpaid balance over 90 days.',
        ]))},
        {"title": "Prioritize Maple for the reminder pilot", "parts": dict(zip(PARTS, [
            f'I find Maple has a {maple["no_show_rate"]:.1%} no-show rate versus '
            f'{harbour["no_show_rate"]:.1%} at Harbour; the difference is {significance} '
            f'(two-sided {p_description}).',
            branch_explanation,
            f'I estimate matching Harbour could retain about {gap["retained_visits"]:.0f} visits/year '
            f'and add {money_k(gap["opportunity_cents"], "CAD/year")} in service revenue, before extra costs. '
            'I do not add this to the group reminder opportunity because they overlap.',
            'I would prioritize Maple for the reminder and confirmation pilot.',
            "I would track Maple's no-show rate and its change against Harbour, split by booking lead time.",
        ]))},
    ]


# I render exactly five labeled paragraphs for each generated finding.
def render_findings(findings):
    lines = ["# Findings", "", "I connect each finding to an action and a measure. "
             "I show money in CAD and keep calculation details in [DETAILS.md](DETAILS.md).", ""]
    for number, finding in enumerate(findings, 1):
        lines.extend([f'## {number}. {finding["title"]}', ""])
        for label in PARTS:
            lines.extend([f'**{label}:** {finding["parts"][label]}', ""])
    return "\n".join(lines)


# I keep exact opportunity calculations alongside the rounded findings.
def update_calculation_details(metrics):
    path = BASE / "DETAILS.md"
    text = path.read_text()
    start, end = "<!-- FINDINGS_CALCULATIONS_START -->", "<!-- FINDINGS_CALCULATIONS_END -->"
    amounts = [
        ("Root-canal service-revenue opportunity per year", metrics["revenue"]["opportunity_cents"]),
        ("Long-lead service-revenue opportunity per year", metrics["lead_time"]["opportunity_cents"]),
        ("Collections working balance", metrics["receivables"]["collections_balance_cents"]),
        ("Cash-recovery opportunity", metrics["receivables"]["opportunity_cents"]),
        ("Prior-year cash timing lift", metrics["receivables"]["previous_year_cash_timing_lift_cents"]),
        ("Maple service-revenue opportunity per year", metrics["branch_gap"]["opportunity_cents"]),
    ]
    table = "| Calculation | Exact estimate |\n|---|---:|\n"
    table += "\n".join(f"| {label} | estimated ${cents / 100:,.2f} CAD |" for label, cents in amounts)
    table += f'\n\nI calculate {metrics["lead_time"]["retained_visits"]:.6f} retained visits/year before rounding. '
    table += "I use full-precision rates and unit values, and round only the displayed findings."
    section = start + "\n" + table + "\n" + end
    if start in text and end in text:
        text = text.split(start)[0] + section + text.split(end, 1)[1]
    else:
        text += "\n## Finding calculations\n\n" + section + "\n"
    path.write_text(text)


# I rebuild the findings document and its supporting numbers from the database.
def build():
    policy = json.loads((BASE / "findings_policy.json").read_text())
    connection = sqlite3.connect(BASE / "processed/dental_clinic.sqlite")
    try:
        connection.execute("PRAGMA temp_store=MEMORY")
        metrics = calculate_metrics(connection, policy)
    finally:
        connection.close()
    findings = make_findings(metrics, policy)
    text = render_findings(findings)
    data = {**metrics, "policy_inputs": policy, "findings": findings}
    (BASE / "FINDINGS.md").write_text(text)
    (BASE / "BUSINESS_QUESTIONS.md").write_text(
        "# Findings\n\nI now keep my four findings, actions and measures in [FINDINGS.md](FINDINGS.md).\n")
    (BASE / "processed/business_findings.json").write_text(json.dumps(data, indent=2))
    update_calculation_details(metrics)
    return data


if __name__ == "__main__":
    build()
