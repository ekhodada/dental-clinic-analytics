# My Power BI build guide

I build the main report in Power BI Desktop on Windows. I start with the Summary page, check its totals, then add the three detail pages.

## 1. Load the tables

1. I copy or clone the whole repository to Windows, for example `C:\Projects\dental-clinic-analytics`. I keep its folders together.
2. I open Power BI Desktop and choose **File → Options and settings → Options → Current File → Data Load**. I turn off **Auto date/time**.
3. I choose **Home → Get data → Text/CSV** and open each of the eight CSV files in this folder. I use comma separation and UTF-8, then **Transform Data**. I keep the query names equal to the filenames without `.csv`.
4. In Power Query, I set these types, then choose **Close & Apply**:

| Type | Columns |
|---|---|
| Date | `dim_date.Date`, `WeekStarting`; `dim_patient.FirstVisit`; fact `AppointmentDate`, `ServiceDate`, `PaymentDate`, `CostDate` |
| Date/Time | `BookedAt`, `ScheduledStart` |
| Whole number | Every `*Cents` column; year, sort, age, minute and day counts; `Chairs` |
| Text | Every ID and all other labels |

I keep money as integer cents and divide by 100 in measures.

| Table | One row means |
|---|---|
| `fact_appointments` | One booking, including cancellations and no-shows |
| `fact_treatments` | One billed service; one visit can have several services |
| `fact_payments` | One receipt; one invoice can have several receipts |
| `fact_expenses` | One expense allocated to one calendar day |
| `dim_date` | One day across the two complete calendar years |
| `dim_location` | One branch |
| `dim_patient` | One registered patient |
| `dim_care_category` | One of the six care categories |

I use [model.json](model.json) for the exact columns and row counts. `ExpenseID` repeats across allocation days; I sum `CostCents`, not an original monthly amount repeated on every day.

## 2. Set the relationships

I open **Model view → Manage relationships**, remove unwanted automatic links, and create these **13 active relationships**. Every relationship is **one-to-many (1:*)**, with **Single** filtering from the dimension to the fact.

| Dimension key, on the 1 side | Fact keys, each on the * side |
|---|---|
| `dim_date.Date` | `fact_appointments.AppointmentDate`, `fact_treatments.ServiceDate`, `fact_payments.PaymentDate`, `fact_expenses.CostDate` |
| `dim_location.LocationID` | `LocationID` in all four facts |
| `dim_patient.PatientID` | `PatientID` in appointments, treatments and payments |
| `dim_care_category.CareCategoryID` | `CareCategoryID` in appointments and treatments |

I do not link fact tables to each other through `AppointmentID` or `InvoiceID`. This avoids multiplying receipts and service lines. Care category means the booked primary category in appointments and the billed category in treatments.

I select `dim_date`, choose **Table tools → Mark as date table**, and select `Date`. I confirm it has 731 unique, nonblank, consecutive dates.

In **Column tools → Sort by column**, I sort:

- `MonthName` by `MonthNumber`; `YearMonth` by `YearMonthSort`; `WeekdayName` by `WeekdayNumber`.
- `ShortName` by `CategorySort`.
- `LeadTimeBand` by `LeadTimeSort`; `AgeGroup` by `AgeGroupSort`.

I hide IDs, cent amounts and sorting columns from Report view after setup. I retain them in the model.

## 3. Add the DAX

1. I choose **Modeling → New table** and paste [tables.dax](tables.dax). I sort `Invoice Age[Age Band]` by `Sort` and leave this table **disconnected**.
2. I create each definition from [measures.dax](measures.dax) separately with **Modeling → New measure**, using `fact_treatments` as its home table. I add `Revenue Prior Year` before measures that reference it. I add `Unpaid Balance by Age` before `Unpaid Over 90 Days`.
3. I format money measures as CAD currency, count measures as whole numbers, and rates as percentages with one decimal. `Profit Detail` and `Summary Headline` stay Text.
4. I load `../processed/reports/recommendations.csv` as `recommendations`, with `Rank` as Whole number. I leave it disconnected and sort its visual by Rank.

The one-line comments explain every measure. `No-show Rate by Lead Time` reuses the main rate: the chart's band and branch fields supply the filters. I divide counts, not an average of branch percentages.

For unpaid bills, I first capture the selected end date, then look back through earlier services and receipts. I match receipts once per invoice with `TREATAS`, ignoring care-category filters so a partial invoice cannot be compared with its whole payment. A 2025 selection still includes unpaid 2024 invoices. The final age band starts at 366 days.

## 4. Build the Summary page

I set **Canvas settings → 16:9**, name the page **Summary**, and optionally import [theme.json](theme.json) through **View → Themes → Browse for themes**.

```text
Operating profit fell 21% vs prior year | what changed?
Year: 2025                         Location: all three branches
┌────────────────┬────────────────┬────────────────┬────────────────┐
│ Revenue        │ Operating      │ Cash collected │ Unpaid over    │
│                │ profit         │                │ 90 days        │
│                │ margin | costs │ receipt dates  │ at period end  │
├─────────────────────┬─────────────────────┬─────────────────────┤
│ Revenue change      │ No-show rate        │ Unpaid bills        │
│ by care category    │ by lead time/branch │ by invoice age      │
├─────────────────────────────────────────────────────────────────┤
│ Ranked actions | Evidence | Estimated value | How to measure    │
└─────────────────────────────────────────────────────────────────┘
```

I use one year, with **Single select** enabled, and the location slicer as my only Summary slicers. I sync these slicers across all four pages. I start at **2025, all branches**. I use a single month or a continuous date range on detail pages, not a scattered month selection.

| Visual | Fields and setup |
|---|---|
| Headline | A Card showing `[Summary Headline]`, with its category label hidden |
| Four cards | `[Revenue]`, `[Operating Profit]`, `[Cash Collected]`, `[Unpaid Over 90 Days]`; display units Thousands, 0 decimals; titles include CAD |
| Profit small text | `[Profit Detail]` as a reference label, or a separate small Card grouped below the profit card |
| Waterfall | Category: `dim_care_category.ShortName`; Y-axis: `[Revenue Change]`; no Breakdown. Title: **Revenue change vs prior year (CAD)**. I keep all six changes and the total: this starts at zero change, not at total prior-year revenue. |
| Clustered column chart | X: `fact_appointments.LeadTimeBand`; Y: `[No-show Rate by Lead Time]`; Legend: `dim_location.LocationName`. Tooltip: completed and missed counts. |
| Column chart | X: `Invoice Age[Age Band]`; Y: `[Unpaid Balance by Age]`; title **Unpaid bills at selected period end (CAD)** |
| Recommendations table | `Rank`, `Action`, `Evidence`, `Estimated annual value`, `How to measure`; ascending Rank, no totals |

I use purple for the report, muted red for decreases, and green for increases. I keep card values large and chart labels readable. On a 1280×720 canvas, I use 24-pixel margins: header/filter rows at the top, cards around y=116, charts around y=232, and the table around y=488.

I label the recommendations **2025 group opportunities — before extra costs**. Their estimates stay at the full-group baseline when slicers change. I use the overlap-adjusted combined range from [FINDINGS.md](../FINDINGS.md), not a sum of the rows; collections are one-off cash, not recurring revenue.

I use **Format → Edit interactions** to stop chart clicks filtering other Summary visuals. The two slicers still filter all analytical visuals. I keep patient and care-category slicers off Summary and Finance: group operating costs cannot be assigned to individual patients or care categories from this model.

## 5. Add the detail pages

| Page | Question and visuals |
|---|---|
| Patients | **Who attends and which care do they use?** Cards: `[Patients Seen]`, `[Completed Visits]`, `[New Patients]`, `[Returning Patients]`. Stacked columns: `fact_appointments.AgeGroup`, `dim_patient.Gender`, `[Patients Seen]`. Care bars: `dim_care_category.ShortName`, `[Patients Treated]`. Branch table: location plus the four cards. |
| Appointments | **Where are bookings being missed?** Cards: scheduled, completed, missed, cancelled and no-show rate. Monthly line chart: `dim_date.YearMonth` plus completed/missed/cancelled measures. Lead-time chart: same as Summary. Branch table: location, completed, missed and rate. |
| Finance | **What did I earn, collect and spend?** Cards: revenue, costs, profit, margin and cash collected. Monthly lines: revenue/costs/profit. Cost bars: `fact_expenses.CostType`, `[Operating Costs]`. Branch table: location plus financial measures. Weekly table: `dim_date.WeekStarting`, revenue/costs/profit/cash collected. I flag boundary weeks as partial. |

Patients can appear in multiple care categories or age groups across years; those counts are not additive. Age is approximate: visit year minus birth year. Completed visits mean care delivered, not a cure. `TreatmentMinutes` excludes turnover; `ReservedMinutes` includes turnaround and original cancelled reservations.

On Finance, I disable interactions from the cost-type bar chart to profit cards and trend charts. Selecting one expense type must not make the remaining costs disappear from a group profit calculation.

For **drill-down**, I create a `dim_date` hierarchy: `Year → Quarter → YearMonth → Date`, put it on the appointment/finance line charts instead of the single month field, and use the visual's drill arrows. I start expanded to month. I keep the chronological sort.

For **drill-through**, I add `dim_location.LocationName` to each detail page's Drill-through well, turn **Keep all filters** off, and add a **Back** button. This passes only the branch; the synced year slicer keeps the period consistent. I right-click a branch column in Summary's no-show chart and choose the detail page, then select a lead-time band there if needed. I also add **Insert → Buttons → Navigator → Page navigator** for simple page switching. I clear temporary drill-through filters before the final save.

## 6. Verify, save and capture

I compare my cards, age chart, rates and category changes with [validation.md](validation.md), first for 2025/all branches and then for each branch. I also check 2024 aging: later receipts must not reduce its year-end balance. These export calculations are checked in Python/SQL; I confirm the measures inside Desktop before recording.

1. I choose **File → Save As**, select Power BI report (`.pbix`), and save `powerbi/Dental Clinic Analytics.pbix` inside my Windows repository copy.
2. For each page, I select 2025/all branches and **View → Page view → Fit to page**. I collapse editing panes, use **Win+Shift+S** to capture only the report canvas, and save a PNG under `docs/images/`:
   - `power-bi-summary.png`
   - `power-bi-patients.png`
   - `power-bi-appointments.png`
   - `power-bi-finance.png`
3. I can also choose **File → Export → Export to PDF** to create one document containing the pages. PDF is not a PNG export.
4. I follow [walkthrough.md](walkthrough.md) for a 1–2 minute recording. I save it as `docs/walkthrough-power-bi.mp4` and link it from the main README after recording.

I commit the PBIX, four PNGs and recording after checking them. On the next pipeline run, the main README detects `power-bi-summary.png`; until then it keeps the report screenshot marked pending.

## Refresh

I follow the [Python setup](../DETAILS.md#how-to-refresh), then run the existing full pipeline. Its dashboard/report step refreshes these CSVs too:

```bash
python -m dental_analytics.clean_and_refresh
python -m dental_analytics.build_dashboard_data
```

On Windows I then click **Home → Refresh** in Desktop and save the PBIX again. If the project moved, I update the CSV paths under **File → Options and settings → Data source settings → Change Source**. I do not merge fact queries in Power Query.

## Microsoft references

I follow Microsoft's [relationship guidance](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-relationships-understand), [date-table setup](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-date-tables), [DATEADD reference](https://learn.microsoft.com/en-us/dax/dateadd-function-dax), [TREATAS reference](https://learn.microsoft.com/en-us/dax/treatas-function-dax), [waterfall setup](https://learn.microsoft.com/en-us/power-bi/visuals/power-bi-visualization-waterfall-charts), [Desktop installation](https://learn.microsoft.com/en-us/power-bi/fundamentals/desktop-get-the-desktop) and [PDF export instructions](https://learn.microsoft.com/en-us/power-bi/consumer/end-user-pdf).
