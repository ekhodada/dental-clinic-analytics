# Simple dashboard guide

## Filters and comparisons

Year, month and branch filters apply to the current page. Each chart point is **one month**; only some axis labels are printed. Selecting a point filters to that month. Comparisons use the same period and branches: 2025 versus 2024, or March 2025 versus March 2024. There is no 2023 baseline. Reset shows all dates and branches.

## Patient Overview

| Term | Meaning |
|---|---|
| Unique patients seen | Different people with a completed visit. Each person counts once across selected branches. |
| Completed visit | Care was delivered; it does not mean the patient was cured or finished treatment. |
| New patient | First-ever visit was inside the selected period. |
| Returning patient | First-ever visit was before the selected period. |
| Attendance rate | Completed ÷ (completed + no-show). Cancellations are excluded. |
| Average age | Approximate age from birth year; each person counts once at their first selected visit. |
| Patients by category | People receiving that care; one person may use several categories. |
| Services completed | Billed procedures; a visit can include more than one. |
| Net service charges | Charges after discounts and adjustments, before operating costs. |

A person seen twice at Harbour and once at Meadow counts as **one group patient and three visits**, and once in each branch. Do not add branch patient counts. Monthly patient counts are not additive either. New plus returning equals unique patients within one selected period.

## Key Trends

| Term | Meaning |
|---|---|
| Scheduled appointment | Any booking: completed, missed or cancelled. |
| No-show | Patient did not attend and had not cancelled. |
| Late cancellation | Less than 24 hours before the planned start. |
| Turnover / turnaround | Cleaning and preparing the chair between patients; ten minutes in the model. |
| Available clinical time | Dentist and hygienist blocks, excluding recorded lunch and leave. Support staff are excluded. |
| Actual care utilization | Completed treatment minutes ÷ available clinical minutes. |
| Booked capacity | Originally reserved minutes, including turnaround, ÷ available clinical minutes. Cancelled bookings remain included. |
| Recall plan | Expected return date after hygiene care, not a recorded phone call. |
| Grace period | An extra 60 calendar days after the expected return date. |
| Overdue recall | Latest return plan plus grace has passed. It does not mean debt, punishment or confirmed churn. |

Two clinicians working eight hours provide 16 clinical hours. A 51% utilization means 51% was direct care. The rest may include preparation, other useful work and unused time; it is not all wasted.

The weekday heatmap groups every Monday in a month together, every Tuesday together, and so on. It divides total reserved minutes by total available minutes.

Returning-patient counts are not a retention rate. The fixed synthetic patient pool causes late-period new-patient counts to fall; this is not evidence of real seasonality or marketing failure. Recall counts also reflect plans becoming observable within the data window.

## Treatment & Costs

See [the financial guide](FINANCIAL_MODEL.md). Main profit is before estimated collection losses. The optional scenario is separate. Revenue by treatment is not treatment profit: costs have not been allocated by procedure.

Weeks start on Monday. A star marks a partial week. The table shows the latest 12 selected weeks; Download all weeks exports every selected week. Profit and cash differ because payment dates differ from service and expense periods.

## Short interview explanation

“I built a reporting process for a three-location dental case study. I cleaned separate exports, checked that records and money totals matched, and created three dashboard pages. I used them to identify service demand, appointment issues and why profit fell. I kept cash separate from profit, explained the assumptions and proposed measurable follow-up actions.”
