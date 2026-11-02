# Data notes

I use the 2024–2025 reporting window, CAD and Toronto local time.

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

## Definitions

I keep all assumptions in [DETAILS.md](DETAILS.md#assumptions).

## Reports

Base reports cover weekly finance, patient trends, care categories, capacity, invoice balances and recall snapshots. Additional reports cover monthly/annual finance, invoice aging and the optional weekly loss scenario.

The live dashboard is a published snapshot. Local refresh and publication are separate. Human review remains necessary; weekly scheduling and automatic external delivery are not configured.
