# Data notes

**Synthetic case study. No real patient records or client results.** The reporting window is January 1, 2024–December 31, 2025; CAD and Toronto local time.

## Data structure

| File | One row means |
|---|---|
| patients.csv | An anonymous patient |
| appointments.csv | A booking, including cancelled and missed visits |
| treatments.csv | A completed billed service |
| payments.csv | A receipt against an invoice |
| expenses.csv | A cost covering a period, with a separate payment date |
| availability.csv | A dentist or hygienist working block |
| recalls.csv | A return plan after hygiene care |
| dates.csv | A calendar date, generated from settings |
| locations.csv | A branch |

There are eight main tables plus the three-row location list. The data includes 10,000 patient records, 40,000 bookings, six dentists and six hygienists. Each site has four chairs; support staff appear in expenses.

Amounts in CSVs are dollars with two decimals. Financial calculations use integer cents where exact reconciliation is needed. Dates use YYYY-MM-DD. [Every field explained](column_guide.csv).

## Relationships

Patient ID links bookings to patients. Session ID links bookings to a provider and available time. Appointment ID links treatments to completed care. Invoice ID links treatment charges to receipts.

An invoice can have several treatment lines and payments. Aggregate them separately before joining; otherwise totals can multiply. Patient home branch and attended branch are different concepts. Costs are assigned to branches and periods, not individual treatments.

## Refresh

Replace raw files with a complete snapshot, not an unchecked weekly append. Use stable IDs and the same columns. Run both steps from the README.

The cleaner standardizes formats, removes identical duplicates and checks references and calculations. Conflicting IDs or new invalid records block publication. Only six named demo errors may be isolated; remove this allowance for a real deployment. Failed base validation preserves previously published clean data.

The date table is generated. Monthly costs are spread across calendar days with exact cent allocation. Shared administration is split equally among branches. Depreciation is noncash. Some December expenses are paid in January; cash uses the payment date.

## Important assumptions

- All branches are leased; staffing, fees and wages are simulated. Dentist compensation is 34% of branch revenue, not a market benchmark.
- Main profit is before estimated collection losses. The optional scenario is separately documented in [the financial guide](FINANCIAL_MODEL.md).
- Higher missed-visit probability for longer booking lead times, an extra Maple no-show effect and an extra Meadow cancellation effect were intentionally built into the simulation. Findings illustrate analysis, not proof of real clinic behaviour.
- The fixed patient pool causes new-patient counts to approach zero late in the period. Do not infer marketing failure or seasonal demand from this.
- Recall plans start within the observation window, so the early rise in overdue counts partly reflects plans becoming due. Overdue is not churn.
- Recall intervals and the 60-calendar-day grace period are simulated business rules, not clinical recommendations.
- Diagnoses, clinical outcomes, contractual invoice due dates, campaigns and intervention results are absent.
- Source fees are not an Ontario fee guide. No real-world revenue, retention or savings improvement has been demonstrated.

## Reports

Base reports cover weekly finance, patient trends, care categories, capacity, invoice balances and recall snapshots. Additional reports cover monthly/annual finance, invoice aging and the optional weekly loss scenario.

The live dashboard is a published snapshot. Local refresh and publication are separate. Human review remains necessary; weekly scheduling and automatic external delivery are not configured.
