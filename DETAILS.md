# Details

## Data and tables

I run reports as SQL views in SQLite, so no database server is needed; the same SQL can run in SQL Server or MySQL with small date-function and syntax changes.

I use 40,000 appointments, CAD, Toronto time and a generated calendar.

I use patients (one person), appointments (one booking), treatments (one service), payments (one receipt), expenses (one cost period), availability (one working block), recalls (one plan), generated dates (one day) and locations (one branch).

I aggregate services and receipts before joining to prevent multiplied totals. [Field definitions](column_guide.csv).

## Cleaning and checks

I standardize dates, labels and money; remove 100 identical duplicates; and isolate six named test errors. Unexpected errors or conflicting IDs block publication and preserve the prior clean outputs.

I retain 34 base checks and cent-level financial checks across 72 branch-months. I also test repeatability, rejected-input protection, age boundaries, follow-up windows, chair-time counting, statistical symmetry, generated findings and recommendation overlap. I save evidence in `processed/*checks*`.

## Metric definitions

- I count distinct patients once across selected branches; branch/month totals are not additive. Completed visits mean care delivered, not a cure; services can outnumber visits.
- I separate new patients, whose first visit falls inside the selection, from returning patients. I estimate age from birth year.
- I calculate attendance as completed ÷ (completed + no-shows); cancellations are separate. I use no-shows as the numerator for the no-show rate. Late cancellation means under 24 hours.
- I divide direct-care minutes by available dentist/hygienist minutes for utilization. Booked capacity includes original cancelled reservations and ten-minute turnaround; support staff are excluded.
- I flag the latest recall after its due date plus 60 calendar days; this is not churn.
- I use monthly chart points and matching prior-year comparisons. Weeks start Monday; partial weeks are marked.
- I calculate eligible 6/12-month return rates only when the first visit and full window are observed; same-day visits are not returns and empty denominators stay blank.
- I split revenue change into volume change × prior average charge and average-charge change × current volume. For chair-hours, I assign each whole visit and invoice once to its primary category.

## Financial method

I recognize service revenue after discounts and adjustments. Operating profit equals revenue minus recorded operating costs, before estimated collection losses, financing costs and tax; margin equals profit ÷ revenue.

I use receipt/payment dates for operating cash surplus. Unpaid charges already belong to revenue; collecting them later does not create revenue again. I separate unpaid selected visits from all outstanding invoices at the cutoff. Aging uses receipts known at that date, and its last band starts at 366 days.

I allocate monthly costs over calendar days with exact residual cents and split shared administration equally. Depreciation is noncash.

I check: **profit + depreciation − increase in unpaid bills + increase in payables, net of prepayments = operating cash surplus**. The separate loss scenario deducts only the change in its allowance and adds it back in the cash bridge. [Annual totals](processed/reports/annual_financials.csv) and [exact finding calculations](processed/business_findings.json) remain available.

## Assumptions

- I use leased sites, six dentists, six hygienists and four chairs per site; dentist compensation is 34% of branch revenue. Tracked opening receivables/payables are zero; taxes, debt, capital purchases, opening bank cash and owner withdrawals are outside scope.
- I set recovery targets, reminders and losses in policy files. Opportunities exclude extra costs; backlog collections are one-off cash.
- I bound shared Maple reminder recoveries, subtract their value once and round the displayed range outward. I assume root-canal recovery uses separate accepted bookings and would audit appointment IDs before combining benefits.
- I retain the fixed patient pool, limited recall history and encoded lead-time/branch patterns. I do not infer marketing failure or clinical outcomes.
- I use a pooled booking-level z-test without patient clustering or lead-time adjustment; significance does not establish cause. Referral, acceptance and payer-error measures require additional fields.

## How to refresh

I use Python 3.12+, replace `raw/` with a complete snapshot using stable IDs, then run:

```bash
python3 -m pip install -e . -r requirements-dev.txt
python3 -m dental_analytics.clean_and_refresh
python3 -m dental_analytics.build_dashboard_data
python3 -m pytest
python3 -m dental_analytics.check_notebook
```

I review checks before pushing; GitHub Pages publishes from `main`.

I time base cleaning/SQL separately in `processed/refresh_log.json`, excluding extra tests and review.

## File map

- `raw/`, `processed/clean/`: source and checked exports.
- `processed/reports/`: analyses, finances and recommendations.
- `code/`: pipeline, installed as `dental_analytics`; `tests/`: 34 quality tests.
- `notebooks/exploration.ipynb`: my exploratory analysis.
- `settings.json`, `*_policy.json`: schema and inputs.
- `dashboard/`: web viewer with aggregate filter summaries.
- `docs/`: walkthrough, screenshots and [process evidence](docs/evidence.html).
- [FINDINGS.md](FINDINGS.md): findings and ranked actions.
