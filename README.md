# Dental Clinic Analytics

Built on a simulated dataset modelled on a 3-branch dental group (10,000 patients, 2024-2025).

**The problem:** A 3-branch dental group's operating profit fell 21% in 2025. Why, and what should it do?

| Finding | Evidence | Action | Estimated value |
|---|---|---|---|
| Fewer root canals | 26% fewer services; 55% of revenue decline | I check referrals and unbooked plans | estimated ~$48K CAD/year |
| Long-lead no-shows | 9.3% versus 3.0% | I pilot reminders and confirmations | estimated ~$57K CAD/year |
| Older unpaid bills | estimated ~$447K CAD aged over 90 days | I triage bills by payer | estimated ~$17K CAD cash; one-off |

## Dashboard

Power BI Summary: I will add its screenshot after I build the report.

[90-second walkthrough GIF — web viewer](docs/walkthrough-web.gif)

[Interactive web version for viewing without a Power BI license](https://ekhodada.github.io/dental-clinic-analytics/)

## How I built it

- I clean exports and run **34 data-quality checks**.
- I analyze revenue, bookings and collections through **SQL reporting views**.
- I reconcile profit to cash **to the cent across 72 branch-months**.
- I automate the **base refresh in about 10 seconds**.

**Tools:** Python, SQL, Power BI

[Method, definitions and refresh instructions](DETAILS.md) · [Findings and ranked actions](FINDINGS.md)
