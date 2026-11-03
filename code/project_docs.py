"""I keep the short project overview aligned with checked reporting results."""

from pathlib import Path
import json
from .business_questions import money_k

BASE = Path(__file__).resolve().parents[1]


# I generate the one-screen overview from the same figures used in the findings.
def render_readme(metrics, quality, financial, media, summary_image=None):
    """I generate the one-screen overview from the same figures used in the findings."""
    revenue, lead, debt = metrics["revenue"], metrics["lead_time"], metrics["receivables"]
    seconds = round(quality["Run Seconds"] / 10) * 10
    summary = (
        f"![Power BI Summary]({summary_image})"
        if summary_image
        else "Power BI Summary: I will add its screenshot after I build the report."
    )
    workflow = "https://github.com/ekhodada/dental-clinic-analytics/actions/workflows/ci.yml"
    badge = f"[![Pipeline and tests]({workflow}/badge.svg)]({workflow})"
    return f"""# Dental Clinic Analytics

Built on a simulated dataset modelled on a 3-branch dental group (10,000 patients, 2024-2025).

{badge}

**The problem:** A {lead['branch_count']}-branch dental group's operating profit fell\
 {revenue['profit_drop_rate']:.0%} in {metrics['year']}. Why, and what should it do?

| Finding | Evidence | Action | Estimated value |
|---|---|---|---|
| Fewer root canals | {revenue['root_service_drop_rate']:.0%} fewer services;\
 {revenue['root_revenue_drop_share']:.0%} of revenue decline |\
 I check referrals and unbooked plans | {money_k(revenue['opportunity_cents'], 'CAD/year')} |
| Long-lead no-shows | {lead['bands']['30+ days']['rate']:.1%} versus\
 {lead['bands']['0-6 days']['rate']:.1%} | I pilot reminders and confirmations |\
 {money_k(lead['opportunity_cents'], 'CAD/year')} |
| Older unpaid bills | {money_k(debt['over_90_days_cents'])} aged over 90 days |\
 I triage bills by payer | {money_k(debt['opportunity_cents'], 'CAD cash; one-off')} |

## Dashboard

{summary}

[{media['duration_seconds']}-second walkthrough GIF — web viewer]({media['path']})

[Interactive web version for viewing without a Power BI license]\
(https://ekhodada.github.io/dental-clinic-analytics/)

## How I built it

- I clean exports and run **{quality['Checks Passed']} data-quality checks**.
- I analyze revenue, bookings and collections through **SQL reporting views**.
- I reconcile profit to cash **to the cent across\
 {financial['branch_months_checked']} branch-months**.
- I automate the **base refresh in about {seconds} seconds**.

**Tools:** Python, SQL, Power BI

[Method, definitions and refresh instructions](DETAILS.md) ·\
 [Findings and ranked actions](FINDINGS.md)
"""


# I refresh the overview after data and financial checks have produced their evidence.
def build():
    """I refresh the overview after data and financial checks have produced their evidence."""
    metrics = json.loads((BASE / "processed/business_findings.json").read_text())
    quality = json.loads((BASE / "processed/refresh_log.json").read_text())
    financial = json.loads((BASE / "processed/financial_checks.json").read_text())
    media = json.loads((BASE / "docs/walkthrough-meta.json").read_text())
    summary = "docs/images/power-bi-summary.png"
    image = summary if (BASE / summary).exists() else None
    (BASE / "README.md").write_text(render_readme(metrics, quality, financial, media, image))


if __name__ == "__main__":
    build()
