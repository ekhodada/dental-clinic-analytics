"""Refresh three business answers directly from the checked reporting database."""
from pathlib import Path
import sqlite3, json
from analysis_stats import branch_noshow_test

BASE=Path(__file__).resolve().parents[1]
# I refresh the business answers and booking-rate comparison from checked reports.
def build():
    db=sqlite3.connect(BASE/'processed/dental_clinic.sqlite')
    db.execute('PRAGMA temp_store=MEMORY')
    latest=db.execute('SELECT MAX(substr(Date,1,4)) FROM dates').fetchone()[0]
    previous=str(int(latest)-1)
    care=db.execute('''SELECT t."Care Category",COUNT(DISTINCT a."Patient ID"),COUNT(*),
        SUM(CAST(ROUND(t."Net Charge"*100) AS INTEGER))/100.0
        FROM treatments t JOIN appointments a USING("Appointment ID")
        WHERE substr(a."Scheduled Start",1,4)=? GROUP BY 1 ORDER BY 3 DESC''',(latest,)).fetchall()
    activity=db.execute('''SELECT substr("Scheduled Start",1,4),COUNT(*),
        SUM(Status='Completed'),SUM(Status='No-show'),SUM(Status='Cancelled')
        FROM appointments GROUP BY 1 ORDER BY 1''').fetchall()
    branches=db.execute('''SELECT l."Location Name",COUNT(*),SUM(a.Status='Completed'),
        SUM(a.Status='No-show'),SUM(a.Status='Cancelled') FROM appointments a
        JOIN locations l USING("Location ID") WHERE substr(a."Scheduled Start",1,4)=?
        GROUP BY l."Location ID"''',(latest,)).fetchall()
    capacity=db.execute('''SELECT SUM("Treatment Minutes"),SUM("Available Minutes")
        FROM capacity WHERE substr(Month,1,4)=?''',(latest,)).fetchone()
    # Calendar-year totals use monthly reports, rather than assigning boundary weeks to one year.
    import csv
    with (BASE/'processed/reports/annual_financials.csv').open() as f: years=list(csv.DictReader(f))
    current=next(x for x in activity if x[0]==latest)
    a=next(x for x in years if x['Year']==previous); b=next(x for x in years if x['Year']==latest)
    patient_count=db.execute('''SELECT COUNT(DISTINCT "Patient ID") FROM appointments
        WHERE Status='Completed' AND substr("Scheduled Start",1,4)=?''',(latest,)).fetchone()[0]
    overdue=db.execute('SELECT SUM("Overdue Patients") FROM recall_trends WHERE Month=?',(latest+'-12',)).fetchone()[0]
    revenue_drop=float(a['Service Revenue'])-float(b['Service Revenue'])
    cost_drop=float(a['Operating Costs'])-float(b['Operating Costs'])
    profit_drop=float(a['Operating Profit'])-float(b['Operating Profit'])
    assert round(revenue_drop-cost_drop,2)==round(profit_drop,2)
    care_total=sum(x[2] for x in care)
    routine=next(x for x in care if x[0]=='Routine & Preventive Care')
    data={'year':latest,'patients':patient_count,'care_categories':care,'activity':activity,
        'branch_activity':branches,'treatment_minutes':capacity[0],'available_minutes':capacity[1],
        'overdue_recall_patients':overdue,'financial_years':years,'profit_bridge_difference':round(revenue_drop-cost_drop-profit_drop,2)}
    data['noshow_comparison_2025'] = branch_noshow_test(db)
    (BASE/'processed/business_findings.json').write_text(json.dumps(data,indent=2))
    branch_table='\n'.join(f'| {name} | {miss/(complete+miss):.1%} | {cancel/bookings:.1%} |' for name,bookings,complete,miss,cancel in branches)
    text=f'''# Three business questions and answers

I compare {latest} with the full previous year across all three branches.

## 1. Which services do our patients use most?

**Dashboard:** Patient Overview.

**What I found:** Routine and preventive care accounts for **{routine[2]:,} of {care_total:,} completed services ({routine[2]/care_total:.1%})**, used by **{routine[1]:,} of {patient_count:,} patients ({routine[1]/patient_count:.1%})**. It generates **${routine[3]:,.0f}** in service revenue.

**What I recommend:** Protect hygiene and check-up availability. Review demand and waiting times before changing appointment blocks. Service volume alone does not establish treatment profitability or clinical need.

**What I will measure:** Recall bookings completed, waiting time and clinical utilization. Do not increase treatments purely to raise revenue.

![Patient Overview](docs/images/07-patient-overview.png)

## 2. Where should we investigate missed visits and unused capacity?

**Dashboard:** Key Trends.

**What I found:** Of **{current[1]:,} bookings**, **{current[2]:,} were completed**, **{current[3]:,} were missed**, and **{current[4]:,} were cancelled**. The missed-visit rate is **{current[3]/(current[2]+current[3]):.1%}** of completed plus missed bookings. Direct care uses **{capacity[0]/capacity[1]:.1%}** of available dentist and hygienist time.

| Branch | Missed / completed + missed | Cancelled / all bookings |
|---|---:|---:|
{branch_table}

**What I recommend:** Investigate Maple's missed visits and Meadow's cancellations first. Review booking lead time and cancellation reasons. Pilot reminders and a consent-based short-notice waitlist; compare with similar appointment groups that did not receive the reminder before claiming an improvement.

**What I will measure:** Missed-visit rate, cancellation rate, cancelled slots refilled and actual care utilization. Non-treatment time also includes preparation and other useful work; it is not automatically wasted time.

There are **{overdue:,} overdue recall patients** at year-end. Review their latest plans and future bookings before contacting them. This is not a churn count.

![Key Trends](docs/images/08-key-trends.png)

## 3. Why did operating profit fall, and is cash also positive?

**Dashboard:** Treatment & Costs.

**What I found:** Service revenue fell by **${revenue_drop:,.0f}**, while recorded operating costs fell by only **${cost_drop:,.0f}**. The difference explains the **${profit_drop:,.0f}** fall in operating profit. Rent and several staff cost categories are unchanged in the model, so costs do not fall as quickly as revenue.

| Measure | {previous} | {latest} |
|---|---:|---:|
| Service revenue | ${float(a['Service Revenue']):,.0f} | ${float(b['Service Revenue']):,.0f} |
| Operating costs | ${float(a['Operating Costs']):,.0f} | ${float(b['Operating Costs']):,.0f} |
| Operating profit, before estimated collection losses | ${float(a['Operating Profit']):,.0f} | ${float(b['Operating Profit']):,.0f} |
| Operating margin, same basis | {float(a['Operating Margin']):.1%} | {float(b['Operating Margin']):.1%} |
| Operating cash surplus | ${float(a['Operating Cash Surplus']):,.0f} | ${float(b['Operating Cash Surplus']):,.0f} |

**What I recommend:** Review weekly branch revenue and controllable costs together. Investigate unfilled appointment slots and older unpaid bills before adding marketing spend. Profit is positive on the stated basis, but collections still need attention.

**What I will measure:** Weekly profit and margin, actual operating cash surplus, and unpaid bills by age. The optional collection-risk scenario is separate from recorded results and is not evidence of actual losses.

![Treatment & Costs](docs/images/09-treatment-costs.png)

## What this project demonstrates

Business questions → clear data definitions → repeatable cleaning → checked reports → interactive dashboards → findings → actions → measures for follow-up.

I use these findings to propose actions and follow-up measures. I keep my assumptions in [DETAILS.md](DETAILS.md#assumptions).
'''
    (BASE/'BUSINESS_QUESTIONS.md').write_text(text)
    db.close()
    return data

if __name__=='__main__': build()
