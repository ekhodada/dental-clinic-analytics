"""Accrual, collection-risk and cash reconciliation in integer CAD cents.

No source amounts are changed. Aging uses service date (not contractual overdue
date). Loss rates are explicit portfolio assumptions, not industry benchmarks.
"""
from pathlib import Path
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import csv, json, re

BASE = Path(__file__).resolve().parents[1]
def cents(value):
    return int((Decimal(str(value))*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
def rows(name):
    with (BASE/'processed/clean'/f'{name}.csv').open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))
def write(name, data):
    with (BASE/'processed/reports'/f'{name}.csv').open('w', newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(data[0])); w.writeheader(); w.writerows(data)
def build():
    config=json.loads((BASE/'settings.json').read_text())
    start=date.fromisoformat(config['start_date']); end=date.fromisoformat(config['end_date'])
    policy=json.loads((BASE/'financial_policy.json').read_text())
    bands=policy['age_bands']
    assert [x['max_days'] for x in bands]==sorted({x['max_days'] for x in bands})
    assert all(0<=x['loss_rate']<=1 for x in bands)
    assert bands[-1]['max_days']>=(end-start).days
    A={x['Appointment ID']:x for x in rows('appointments')}
    invoices={}; events=defaultdict(list)
    for t in rows('treatments'):
        a=A[t['Appointment ID']]; key=t['Invoice ID']
        v=invoices.setdefault(key,{'date':a['Scheduled Start'][:10], 'loc':a['Location ID'], 'bill':0})
        v['bill']+=cents(t['Net Charge'])
    for p in rows('payments'): events[p['Invoice ID']].append((p['Payment Date'],cents(p['Amount'])))
    expenses=rows('expenses'); locations=rows('locations')
    monthly=[]; aging=[]; provision=[]; checks=[]; prev={l['Location ID']:(0,0,0) for l in locations}
    import sqlite3
    db=sqlite3.connect(BASE/'processed/dental_clinic.sqlite'); db.execute('PRAGMA temp_store=MEMORY')
    d=start
    while d<=end:
        next_month=date(d.year+1,1,1) if d.month==12 else date(d.year,d.month+1,1)
        cutoff=min(end,next_month-timedelta(days=1)); lo=d.isoformat(); hi=cutoff.isoformat()
        for l in locations:
            loc=l['Location ID']; balances=[0]*len(bands); gross_ar=allowance=revenue=received=0
            for key,v in invoices.items():
                if v['loc']!=loc or v['date']>hi: continue
                paid=sum(amount for when,amount in events[key] if when<=hi)
                balance=v['bill']-paid; assert balance>=0
                gross_ar+=balance
                age=(cutoff-date.fromisoformat(v['date'])).days
                bi=next(i for i,b in enumerate(bands) if age<=b['max_days'])
                balances[bi]+=balance
                allowance+=int((Decimal(balance)*Decimal(str(bands[bi]['loss_rate']))).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
                if lo<=v['date']<=hi: revenue+=v['bill']
                received+=sum(amount for when,amount in events[key] if lo<=when<=hi)
            allocated=db.execute('SELECT COALESCE(SUM(cents),0) FROM daily_costs WHERE "Location ID"=? AND "Date" BETWEEN ? AND ?', (loc,lo,hi)).fetchone()[0]
            # Depreciation has no payment date and is never a cash outflow.
            depreciation=0; payable=0
            for x in expenses:
                if x['Location ID']!=loc: continue
                amount=cents(x['Amount']); a=date.fromisoformat(x['Cost From']); b=date.fromisoformat(x['Cost To'])
                days=(b-a).days+1; covered=max(0,min(days,(cutoff-a).days+1))
                accrued=(amount//days)*covered+min(amount%days,covered)
                paid_to_date=amount if x['Paid On'] and x['Paid On']<=hi else 0
                if x['Cost Type']=='Depreciation':
                    depreciation+=db.execute('SELECT COALESCE(SUM(cents),0) FROM daily_costs WHERE "Expense ID"=? AND "Date" BETWEEN ? AND ?', (x['Expense ID'],lo,hi)).fetchone()[0]
                else: payable+=accrued-paid_to_date
            cash_paid=sum(cents(x['Amount']) for x in expenses if x['Location ID']==loc and x['Paid On'] and lo<=x['Paid On']<=hi)
            old_ar,old_allow,old_payable=prev[loc]; loss=allowance-old_allow
            profit=revenue-allocated; scenario_profit=profit-loss; cash=received-cash_paid
            bridge=profit+depreciation-(gross_ar-old_ar)+(payable-old_payable)
            assert bridge==cash, (lo,loc,bridge,cash)
            assert scenario_profit+loss+depreciation-(gross_ar-old_ar)+(payable-old_payable)==cash
            assert revenue-received==gross_ar-old_ar
            assert 0<=allowance<=gross_ar
            prev[loc]=(gross_ar,allowance,payable)
            provision.append([hi,loc,loss])
            money=lambda n: format(Decimal(n)/100,'.2f')
            record={'Month':lo[:7],'Location ID':loc,'Service Revenue':money(revenue),'Money Received':money(received),'Operating Costs':money(allocated),'Operating Profit':money(profit),'Operating Margin':round(profit/revenue,6) if revenue else '', 'Scenario Loss Expense':money(loss),'Scenario Operating Profit':money(scenario_profit),'Scenario Operating Margin':round(scenario_profit/revenue,6) if revenue else '', 'Cash Operating Payments':money(cash_paid),'Operating Cash Surplus':money(cash),'Gross Receivables':money(gross_ar),'Scenario Loss Allowance':money(allowance),'Scenario Net Receivables':money(gross_ar-allowance),'Depreciation':money(depreciation),'Operating Payables Less Prepayments':money(payable),'Cash Bridge Difference':'0.00'}
            monthly.append(record)
            for i,b in enumerate(bands): aging.append({'As Of':hi,'Location ID':loc,'Invoice Age':b['label'],'Gross Balance':money(balances[i]),'Assumed Loss Rate':b['loss_rate']})
        d=next_month
    # Main report uses recorded costs. Hypothetical loss provisions stay separate.
    db.execute('DROP VIEW IF EXISTS scenario_weekly_finances')
    db.execute('DROP VIEW IF EXISTS weekly_finances')
    db.execute('DROP VIEW IF EXISTS base_weekly_finances')
    db.execute('DROP TABLE IF EXISTS collection_provisions')
    db.execute('CREATE TABLE collection_provisions (Date TEXT, "Location ID" TEXT, cents INTEGER)')
    db.executemany('INSERT INTO collection_provisions VALUES (?,?,?)',provision)
    sql=(BASE/'code/reports.sql').read_text()
    base_sql=sql[sql.index('CREATE VIEW weekly_finances AS'):sql.index('CREATE VIEW patient_trends AS')]
    db.executescript(base_sql)
    db.executescript('''CREATE VIEW scenario_weekly_finances AS
    WITH loss AS (SELECT d."Week Starting",p."Location ID",SUM(p.cents) cents
      FROM collection_provisions p JOIN dates d ON p.Date=d.Date GROUP BY 1,2)
    SELECT b."Week Starting",b."Location ID",b."Days Included",b."Week Coverage",
      b."Service Revenue",b."Money Received",
      ROUND(b."Operating Costs"+COALESCE(l.cents,0)/100.0,2) "Operating Costs",
      ROUND(b."Operating Profit"-COALESCE(l.cents,0)/100.0,2) "Operating Profit",
      CASE WHEN b."Service Revenue">0 THEN ROUND((b."Operating Profit"-COALESCE(l.cents,0)/100.0)/b."Service Revenue",6) END "Profit Margin"
    FROM weekly_finances b LEFT JOIN loss l USING("Week Starting","Location ID");''')
    db.commit()
    cursor=db.execute('SELECT * FROM weekly_finances'); names=[x[0] for x in cursor.description]
    write('weekly_finances',[dict(zip(names,r)) for r in cursor.fetchall()])
    cursor=db.execute('SELECT * FROM scenario_weekly_finances'); names=[x[0] for x in cursor.description]
    write('scenario_weekly_finances',[dict(zip(names,r)) for r in cursor.fetchall()])
    actual=sum(cents(r['Operating Profit']) for r in monthly)
    weekly_total=cents(db.execute('SELECT SUM("Operating Profit") FROM weekly_finances').fetchone()[0])
    assert actual==weekly_total
    assert sum(cents(r['Scenario Operating Profit']) for r in monthly)==cents(db.execute('SELECT SUM("Operating Profit") FROM scenario_weekly_finances').fetchone()[0])
    db.close()
    write('monthly_financials',monthly); write('receivables_aging',aging)
    annual=[]
    flow_keys=['Service Revenue','Money Received','Operating Costs','Operating Profit','Scenario Loss Expense','Scenario Operating Profit','Cash Operating Payments','Operating Cash Surplus','Depreciation']
    for year in sorted({x['Month'][:4] for x in monthly}):
        records=[x for x in monthly if x['Month'].startswith(year)]
        record={'Year':year,**{k:format(sum(Decimal(x[k]) for x in records),'.2f') for k in flow_keys}}
        last=max(x['Month'] for x in records)
        for k in ['Gross Receivables','Scenario Loss Allowance','Scenario Net Receivables','Operating Payables Less Prepayments']:
            record[k]=format(sum(Decimal(x[k]) for x in records if x['Month']==last),'.2f')
        record['Operating Margin']=round(Decimal(record['Operating Profit'])/Decimal(record['Service Revenue']),6)
        record['Scenario Operating Margin']=round(Decimal(record['Scenario Operating Profit'])/Decimal(record['Service Revenue']),6)
        annual.append(record)
    write('annual_financials',annual)
    guide=BASE/'FINANCIAL_MODEL.md'
    if guide.exists():
        keys=flow_keys+['Gross Receivables','Scenario Loss Allowance','Scenario Net Receivables']
        table='| Measure | '+' | '.join(x['Year'] for x in annual)+' |\n|---|'+'---:|'*len(annual)+'\n'
        table+='\n'.join('| '+k+' | '+' | '.join('$'+format(Decimal(x[k]),',.2f') for x in annual)+' |' for k in keys)
        table+='\n| Operating margin | '+' | '.join(format(Decimal(x['Operating Margin'])*100,'.1f')+'%' for x in annual)+' |'
        table+='\n| Scenario margin | '+' | '.join(format(Decimal(x['Scenario Operating Margin'])*100,'.1f')+'%' for x in annual)+' |'
        text=guide.read_text()
        guide.write_text(re.sub(r'(?s)<!-- ANNUAL_START -->.*?<!-- ANNUAL_END -->','<!-- ANNUAL_START -->\n'+table+'\n<!-- ANNUAL_END -->',text))
    result={'policy':policy,'provisions':provision,'checks':{'monthly_branch_cash_bridges_reconcile':True,'receivables_roll_forward_reconciles':True,'scenario_allowances_within_gross_balances':True,'main_and_scenario_weekly_monthly_profit_match':True,'branch_months_checked':len(monthly)},'monthly':monthly,'aging':aging}
    (BASE/'processed/financial_checks.json').write_text(json.dumps(result['checks'],indent=2))
    return result

if __name__=='__main__':
    r=build(); print(json.dumps(r['checks'],indent=2))
