# Analysis details

I refresh six analysis views and their CSVs with the existing pipeline. I save the booking comparison in `processed/business_findings.json` and validation results in `processed/analysis_checks.json`.

## Reports

| SQL view / CSV | What I measure |
|---|---|
| revenue_bridge | 2024 versus 2025 service counts, revenue, volume effect and average-charge effect by billed care category. |
| noshow_by_lead_time | 2025 branch no-shows divided by completed plus no-show bookings, by whole-day booking lead time. |
| receivables_by_age | Invoice balances after receipts through December 31, 2025, grouped by age since care. |
| revenue_per_chair_hour | 2025 whole-visit revenue divided by actual treatment hours, grouped by primary appointment category. |
| channel_value | Registered patients, eligible 12-month return rate and revenue per patient by acquisition channel. |
| retention_cohorts | First-visit quarters with eligible patient counts and 6- and 12-month return rates. |

I use `patient_followup` as an internal helper view. Rates are fractions from 0 to 1 in CSVs: 0.03 means 3%. Money columns end in `_cad`; time columns state hours.

## Numbers I verified

| Measure | Result |
|---|---:|
| Root canal services, 2024 → 2025 | 280 → 208 services |
| Root canal revenue change | −$95,540.74 CAD |
| Total revenue change | −$172,222.90 CAD |
| Volume effect | −$171,143.10 CAD |
| Average-charge effect | −$1,079.80 CAD |
| Routine average charge, 2024 → 2025 | $144.87 → $144.81 CAD/service |
| 0–6-day lead time | 142 / 4,746 appointments = 3.0% no-shows |
| 7–29-day lead time | 390 / 8,429 appointments = 4.6% no-shows |
| 30+-day lead time | 457 / 4,914 appointments = 9.3% no-shows |
| Root canal revenue per treatment hour | $807.08 CAD/hour |
| Routine revenue per treatment hour | $255.01 CAD/hour |

I calculate volume effect as (2025 count − 2024 count) × 2024 average charge. I calculate price effect as (2025 average charge − 2024 average charge) × 2025 count. I use full precision before rounding the effects to cents; the rounding-difference column records any residual.

I find broadly stable average charges, rather than identical prices. Alignment has the largest average-charge move, from $269.50 to $263.99 CAD/service, about −2.05%. The exact query is:

```sql
SELECT care_category, average_charge_2024_cad, average_charge_2025_cad,
       volume_effect_cad, price_effect_cad
FROM revenue_bridge;
```

## Aging totals and the small target differences

I get $633,324.86 CAD unpaid in total, $447,077.48 CAD over 90 days, and $380,975.92 CAD over 180 days. I sum cents before rounding. To the nearest dollar, the latter two are $447,077 CAD and $380,976 CAD. Adding rounded bands gives $447,078 CAD for the over-90-day total; truncating the over-180-day total gives $380,975 CAD. I keep the cent-based totals as the source of truth.

```sql
SELECT
  ROUND(SUM(unpaid_balance_cad), 2) AS total_unpaid_cad,
  ROUND(SUM(CASE WHEN invoice_age_band IN
    ('91-180 days','181-365 days','366+ days')
    THEN unpaid_balance_cad ELSE 0 END), 2) AS over_90_days_cad,
  ROUND(SUM(CASE WHEN invoice_age_band IN
    ('181-365 days','366+ days')
    THEN unpaid_balance_cad ELSE 0 END), 2) AS over_180_days_cad
FROM receivables_by_age;
```

## Booking-rate comparison

I compare Maple's 375 / 5,969 eligible appointments (6.3%) with Harbour's 282 / 6,114 eligible appointments (4.6%). I get z = 4.047735 and a two-sided p-value of 0.0000517156. The gap is 1.67 percentage points.

I pool the two rates to calculate the standard error. I calculate the two-sided normal-tail probability with `math.erfc`, so I need no external package. I do not interpret this unadjusted booking comparison as proof of a branch causing no-shows.

## Assumptions

- I recognize completed-care revenue after discounts and adjustments. I keep unpaid bills in revenue. Main profit is before estimated collection losses; I keep the existing expected-loss scenario separate.
- I use billed service categories for the revenue bridge, but assign each full invoice and its treatment time once to the visit's primary appointment category for chair-hours. Shared diagnostic services explain the category differences. “Price effect” also includes changes in procedure mix and discounts.
- I age invoices at December 31, 2025 using receipts known by that date. My last band starts at 366 days, so day 365 belongs only to the 181–365-day band.
- I count all registered patients in channel totals, including patients with no observed revenue. Revenue per patient covers the reporting window; I also export first-12-month revenue per eligible patient for a fairer comparison.
- I include a patient in a return-rate denominator only when the first visit is observed and the full 6- or 12-calendar-month window is available. I clamp month-end anniversaries, count returns on later dates across all branches, exclude pre-window histories, and leave rates blank when nobody is eligible.
- I use a pooled, two-sided booking-level z-test without continuity correction. Repeated patients and differences in booking lead time are not adjusted. A small p-value does not establish a cause.
- I keep the existing observation limits: a fixed patient pool affects late new-patient counts, recall history starts inside the window, and selected lead-time and branch patterns are built into the records. Recommendations remain proposals.
- I retain leased sites, six dentists, six hygienists and dentist compensation at 34% of branch revenue. I keep the existing optional loss rates in financial_policy.json as scenario inputs, not recorded losses.
- I retain the existing financial scope: zero tracked opening receivables/payables; no opening bank cash, taxes, borrowing, capital purchases or owner withdrawals. Clinical outcome, campaign and actual intervention results are unavailable.

## Refresh and check

```bash
python3 code/clean_and_refresh.py
python3 code/build_dashboard_data.py
```

I retain all 34 base checks and the profit-to-cash checks for 72 branch-months. I additionally test age-band edges, future receipt exclusion, single-counted chair time, month-end follow-up, same-day visits, incomplete cohorts, revenue totals and z-test symmetry. These extra checks run in the second pipeline step.
