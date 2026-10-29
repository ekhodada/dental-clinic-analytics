from pathlib import Path
import csv,json,sqlite3,shutil
B=Path(__file__).resolve().parents[1]
S=B/"processed"; D=B/"dashboard"
def rows(name):
 with (S/'clean'/f'{name}.csv').open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
P=rows('patients'); A=rows('appointments'); T=rows('treatments'); R=rows('payments'); L=rows('locations'); H=rows('availability');Q=rows('recalls');E=rows('expenses')
from financial_model import build as build_financials, cents
financials=build_financials()
pi={p['Patient ID']:i for i,p in enumerate(P)};ai={a['Appointment ID']:i for i,a in enumerate(A)};li={l['Location ID']:i for i,l in enumerate(L)}
config=json.loads((B/'settings.json').read_text());cats=config['care_categories'];ci={c:i for i,c in enumerate(cats)}
images=['01-preventive-care.png','02-restoration.png','03-gum-care.png','04-root-canal.png','05-surgery-tooth-replacement.png','06-alignment-jaw-care.png']
(D/'images').mkdir(exist_ok=True)

from datetime import datetime
minutes=lambda s,e:round((datetime.fromisoformat(e)-datetime.fromisoformat(s)).total_seconds()/60)
invoices={t['Invoice ID']:ai[t['Appointment ID']] for t in T}
c=sqlite3.connect(S/'dental_clinic.sqlite');c.execute('PRAGMA temp_store=MEMORY')
costs=c.execute('SELECT d.[Date],d.[Location ID],e.[Cost Type],SUM(d.cents) FROM daily_costs d JOIN expenses e USING([Expense ID]) GROUP BY d.[Date],d.[Location ID],e.[Cost Type]').fetchall()
costnames=sorted({x[2] for x in costs});costmap={v:i for i,v in enumerate(costnames)}
available=c.execute('SELECT substr([Work Starts],1,10),[Location ID],SUM([Available Minutes]) FROM availability GROUP BY 1,2').fetchall()
data={'locations':[[l['Location Name'],l['City']] for l in L],'locationIds':[l['Location ID'] for l in L],'categories':cats,'images':images,'costNames':costnames,
 'patients':[[int(p['Birth Year']),p['Gender'],p['First Visit']] for p in P],
 'appointments':[[pi[a['Patient ID']],li[a['Location ID']],a['Scheduled Start'][:10],ci[a['Care Category']],['Completed','Cancelled','No-show'].index(a['Status']),
 minutes(a['Treatment Started'],a['Treatment Finished']) if a['Status']=='Completed' else 0,
 minutes(a['Scheduled Start'],a['Chair Available At']),1 if a['Cancelled At'] and minutes(a['Cancelled At'],a['Scheduled Start'])<1440 else 0] for a in A],
 'treatments':[[ai[t['Appointment ID']],ci[t['Care Category']],round(float(t['Net Charge'])*100)] for t in T],
 'payments':[[invoices[r['Invoice ID']],r['Payment Date'],round(float(r['Amount'])*100)] for r in R],
 'costs':[[d,li[l],costmap[cat],amt] for d,l,cat,amt in costs],
 'cashExpenses':[[x['Paid On'],li[x['Location ID']],cents(x['Amount'])] for x in E if x['Paid On'] and config['start_date']<=x['Paid On']<=config['end_date']],
 'financialMonths':financials['monthly'], 'financialAging':financials['aging'],
 'financialPolicy':financials['policy'],
 'riskCosts':[[d,li[l],amount] for d,l,amount in financials['provisions']],
 'available':[[d,li[l],m] for d,l,m in available],
 'recalls':[[pi[q['Patient ID']],ai[q['Previous Visit ID']],q['Return Due'],int(q['Grace Days'])] for q in Q]}
(D/'data.js').write_text('window.CLINIC_DATA='+json.dumps(data,separators=(',',':'))+';')
from business_questions import build as build_business_answers
build_business_answers()
print('Exported clean source data with explicit collection-loss estimates and cash reconciliation.')
