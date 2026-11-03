"""Clean full CSV snapshots and rebuild the dental reporting database. Python 3.10+."""
from pathlib import Path
from datetime import date,datetime,timedelta
from decimal import Decimal,InvalidOperation
from collections import defaultdict,Counter
import csv,json,sqlite3,time,argparse,hashlib,shutil,os

BASE=Path(__file__).resolve().parents[1]
KEYS={'locations':'Location ID','patients':'Patient ID','availability':'Session ID',
 'appointments':'Appointment ID','treatments':'Treatment Record ID','payments':'Payment ID',
 'expenses':'Expense ID','recalls':'Recall ID'}
MONEY={'Gross Charge','Discount','Adjustment','Net Charge','Amount'}
INTS={'Chairs','Birth Year','Available Minutes','Grace Days'}
DATES={'First Visit','Cost From','Cost To','Paid On','Payment Date','Return Due'}
TIMES={'Work Starts','Work Ends','Booked At','Scheduled Start','Scheduled End','Chair Available At',
 'Cancelled At','Treatment Started','Treatment Finished'}
FK={'patients':{'Home Location ID':('locations','Location ID')},
 'availability':{'Location ID':('locations','Location ID')},
 'appointments':{'Patient ID':('patients','Patient ID'),'Location ID':('locations','Location ID'),'Session ID':('availability','Session ID')},
 'treatments':{'Appointment ID':('appointments','Appointment ID')},
 'expenses':{'Location ID':('locations','Location ID')},
 'recalls':{'Patient ID':('patients','Patient ID'),'Previous Visit ID':('appointments','Appointment ID')}}

def read(path):
 with path.open(encoding='utf-8-sig',newline='') as f:
  c=csv.DictReader(f); return c.fieldnames,list(c)
def write(path,rows,columns=None):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=columns or list(rows[0])); w.writeheader(); w.writerows(rows)
def cents(value): return int(Decimal(str(value))*100)

def refresh(source,output):
 started=time.perf_counter(); config=json.loads((BASE/'settings.json').read_text())
 output.mkdir(parents=True,exist_ok=True)
 # Build in a separate staging folder; failed runs cannot replace the last published data.
 stage=output/'_building'
 if stage.exists(): shutil.rmtree(stage)
 stage.mkdir()
 tables={}; audit={}; rejected=[]
 def reject(table,line,reason,row):
  rejected.append({'Table':table,'CSV Row':line,'Problem':reason,'Original Record':json.dumps(row)})
 for table,key in KEYS.items():
  columns,raw=read(source/f'{table}.csv'); cleaned=[]; changes=Counter(); grouped=defaultdict(list)
  if columns!=config['columns'][table]: raise ValueError(f'{table}: column names/order differ from settings.json')
  parents={col:{v[pk] for v in tables[parent]} for col,(parent,pk) in FK.get(table,{}).items()}
  invoice_keys={x['Invoice ID'] for x in tables.get('treatments',[])}
  for line,original in enumerate(raw,2):
   row={k:v.strip() for k,v in original.items()}
   if row!=original: changes['Rows with extra spaces fixed']+=1
   try:
    if not row[key]: raise ValueError('Missing record ID')
    for col,value in list(row.items()):
     if col in MONEY:
      number=Decimal(value.replace('$','').replace(',','').replace('CAD','').strip())
      if not number.is_finite() or number<0 or number!=number.quantize(Decimal('.01')):
       raise ValueError(f'Invalid amount: {col}')
      row[col]=format(number,'.2f')
      if row[col]!=value: changes['Money formats fixed']+=1
     elif col in INTS:
      row[col]=int(value)
      if row[col]<0: raise ValueError(f'Negative number: {col}')
     elif col in DATES and value:
      try: parsed=date.fromisoformat(value)
      except ValueError: parsed=datetime.strptime(value,'%m/%d/%Y').date()
      row[col]=parsed.isoformat()
      if row[col]!=value: changes['Date formats fixed']+=1
     elif col in TIMES and value: row[col]=datetime.fromisoformat(value).isoformat()
    if table=='appointments':
     statuses={'completed':'Completed','cancelled':'Cancelled','canceled':'Cancelled','no show':'No-show','no-show':'No-show'}
     row['Status']=statuses[row['Status'].lower()]
     if row['Status']!=original['Status']: changes['Appointment labels fixed']+=1
    for col,keys in parents.items():
     if row[col] not in keys: raise ValueError(f'Unknown {col}: {row[col]}')
    if table=='payments' and row['Invoice ID'] not in invoice_keys: raise ValueError('Unknown Invoice ID')
    grouped[row[key]].append((line,row))
   except (ValueError,KeyError,InvalidOperation) as e: reject(table,line,str(e),original)
  duplicates=0
  for keyvalue,items in grouped.items():
   if len({json.dumps(x[1],sort_keys=True) for x in items})>1:
    for line,row in items: reject(table,line,'Conflicting records share an ID',row)
   else:
    cleaned.append(items[0][1]); duplicates+=len(items)-1
  tables[table]=cleaned
  audit[table]={'Raw Rows':len(raw),'Clean Rows':len(cleaned),'Duplicate Rows Removed':duplicates,
   'Rejected Rows':sum(x['Table']==table for x in rejected),'Changes':dict(changes)}
 # Only exact identified synthetic error fixtures are excluded in demonstration mode.
 expected=config.get('demo_rejected_records',{})
 unexpected=[x for x in rejected if str(json.loads(x['Original Record']).get(KEYS[x['Table']],'')) not in expected.get(x['Table'],[])]
 rejectcols=['Table','CSV Row','Problem','Original Record']
 write(output/'rejected_rows.csv',rejected,rejectcols)
 if unexpected: raise ValueError('New invalid records found. See rejected_rows.csv; prior published data preserved.')
 checks=[]
 def check(label,ok): checks.append({'Check':label,'Result':'PASS' if ok else 'FAIL'})
 A={a['Appointment ID']:a for a in tables['appointments']}
 H={h['Session ID']:h for h in tables['availability']}
 P={p['Patient ID']:p for p in tables['patients']}
 start=date.fromisoformat(config['start_date']); end=date.fromisoformat(config['end_date'])
 for table,key in KEYS.items(): check(f'{table}: unique IDs',len({x[key] for x in tables[table]})==len(tables[table]))
 check('Three locations',len(tables['locations'])==3)
 provider_roles=defaultdict(set)
 for h in H.values(): provider_roles[h['Provider ID']].add(h['Provider Type'])
 check('Six dentists and six hygienists',Counter(next(iter(v)) for v in provider_roles.values() if len(v)==1)=={'Dentist':6,'Hygienist':6})
 check('Appointments fit available sessions',all(
  H[a['Session ID']]['Work Starts']<=a['Scheduled Start']<a['Scheduled End']<a['Chair Available At']<=H[a['Session ID']]['Work Ends']
  and a['Location ID']==H[a['Session ID']]['Location ID'] for a in A.values()))
 check('Bookings fall in analysis period',all(start.isoformat()<=a['Scheduled Start'][:10]<=end.isoformat() for a in A.values()))
 check('Booking and cancellation times make sense',all(a['Booked At']<=a['Scheduled Start'] and (not a['Cancelled At'] or a['Booked At']<=a['Cancelled At']<=a['Scheduled Start']) for a in A.values()))
 check('Actual treatment times match attendance',all(
  a['Scheduled Start']<=a['Treatment Started']<a['Treatment Finished']<=a['Chair Available At'] if a['Status']=='Completed'
  else not a['Treatment Started'] and not a['Treatment Finished'] for a in A.values()))
 for label,keyfunc in [('Provider',lambda a:H[a['Session ID']]['Provider ID']),('Chair',lambda a:(a['Location ID'],H[a['Session ID']]['Chair ID'])),('Patient',lambda a:a['Patient ID'])]:
  groups=defaultdict(list)
  for a in A.values(): groups[keyfunc(a)].append(a)
  okay=True
  for group in groups.values():
   group.sort(key=lambda a:a['Scheduled Start'])
   if any(x['Chair Available At']>y['Scheduled Start'] for x,y in zip(group,group[1:])): okay=False
  check(f'{label}: no overlapping bookings',okay)
 check('Availability minutes match work blocks',all(h['Available Minutes']==int((datetime.fromisoformat(h['Work Ends'])-datetime.fromisoformat(h['Work Starts'])).total_seconds()/60) for h in H.values()))
 check('Patients first visit is consistent',all(P[a['Patient ID']]['First Visit']<=a['Scheduled Start'][:10] for a in A.values() if a['Status']=='Completed'))
 T=tables['treatments']; invoice_appointments=defaultdict(set); bill=defaultdict(int); visit_bills=defaultdict(set)
 for t in T:
  invoice_appointments[t['Invoice ID']].add(t['Appointment ID']); visit_bills[t['Appointment ID']].add(t['Invoice ID']); bill[t['Invoice ID']]+=cents(t['Net Charge'])
 check('Treatment charge calculations reconcile',all(cents(t['Gross Charge'])-cents(t['Discount'])-cents(t['Adjustment'])==cents(t['Net Charge']) for t in T))
 check('Treatments belong to completed visits',all(A[t['Appointment ID']]['Status']=='Completed' for t in T))
 check('One invoice per completed visit',set(visit_bills)=={a['Appointment ID'] for a in A.values() if a['Status']=='Completed'} and all(len(x)==1 for x in visit_bills.values()) and all(len(x)==1 for x in invoice_appointments.values()))
 paid=defaultdict(int)
 for p in tables['payments']: paid[p['Invoice ID']]+=cents(p['Amount'])
 check('Invoices are not overpaid',all(paid[k]<=amount for k,amount in bill.items()))
 check('Payment dates are valid',all(A[next(iter(invoice_appointments[p['Invoice ID']]))]['Scheduled Start'][:10]<=p['Payment Date']<=end.isoformat() for p in tables['payments']))
 check('Expense periods covered by calendar',all(start.isoformat()<=x['Cost From']<=x['Cost To']<=end.isoformat() for x in tables['expenses']))
 check('Recall plans match patients and dates',all(A[q['Previous Visit ID']]['Patient ID']==q['Patient ID'] and A[q['Previous Visit ID']]['Status']=='Completed' and q['Return Due']>A[q['Previous Visit ID']]['Scheduled Start'][:10] for q in tables['recalls']))
 check('Six known care categories',set(t['Care Category'] for t in T)==set(config['care_categories']))
 def gate():
  write(output/'quality_checks.csv',checks)
  if any(x['Result']=='FAIL' for x in checks): raise ValueError('Quality checks failed; previous published data preserved.')
 gate()
 days=[]; d=start
 while d<=end:
  days.append({'Date':d.isoformat(),'Week Starting':(d-timedelta(days=d.weekday())).isoformat(),'Month':d.strftime('%Y-%m')}); d+=timedelta(days=1)
 tables['dates']=days
 db=sqlite3.connect(stage/'dental_clinic.sqlite'); db.execute('PRAGMA temp_store=MEMORY'); db.execute('PRAGMA journal_mode=MEMORY')
 for table,rows in tables.items():
  cols=list(rows[0]); pk=KEYS.get(table,'Date')
  types=lambda col:'REAL' if col in MONEY else 'INTEGER' if col in INTS else 'TEXT'
  definitions=','.join(f'"{col}" {types(col)}'+(' PRIMARY KEY' if col==pk else '') for col in cols)
  db.execute(f'CREATE TABLE {table} ({definitions})')
  db.executemany(f'INSERT INTO {table} VALUES ({",".join("?" for _ in cols)})',[[x[col] for col in cols] for x in rows])
  write(stage/'clean'/f'{table}.csv',rows)
 db.executescript((BASE/'code'/'reports.sql').read_text()); db.commit()
 for name in ['weekly_finances','patient_trends','care_summary','capacity','unpaid_invoices','recall_trends']:
  c=db.execute(f'SELECT * FROM {name}'); cols=[x[0] for x in c.description]
  write(stage/'reports'/f'{name}.csv',[dict(zip(cols,row)) for row in c.fetchall()],cols)
 total=lambda query:round(db.execute(query).fetchone()[0]*100)
 check('Weekly revenue matches treatments',total('SELECT SUM("Service Revenue") FROM weekly_finances')==sum(cents(x['Net Charge']) for x in T))
 check('Weekly costs match expenses',total('SELECT SUM("Operating Costs") FROM weekly_finances')==sum(cents(x['Amount']) for x in tables['expenses']))
 check('Weekly collections match payments',total('SELECT SUM("Money Received") FROM weekly_finances')==sum(cents(x['Amount']) for x in tables['payments']))
 check('Unpaid invoice amounts reconcile',total('SELECT SUM("Still Owed") FROM unpaid_invoices')==sum(bill.values())-sum(paid.values()))
 check('Capacity rates do not exceed 100%',db.execute('SELECT COUNT(*) FROM capacity WHERE "Booked Capacity" >1 OR "Treatment Use" >1').fetchone()[0]==0)
 check('Monthly new and returning patients reconcile',db.execute('SELECT COUNT(*) FROM patient_trends WHERE "New Patients"+"Returning Patients"<>"Patients Seen"').fetchone()[0]==0)
 check('SQLite file integrity',db.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
 gate(); db.close()
 # Publish only after every validation and reconciliation succeeds.
 for folder in ['clean','reports']:
  old=output/folder
  if old.exists(): shutil.rmtree(old)
  shutil.move(str(stage/folder),str(old))
 os.replace(stage/'dental_clinic.sqlite',output/'dental_clinic.sqlite'); stage.rmdir()
 result={'Synthetic Data':True,'Input Mode':'Complete snapshot replacement','Tables':audit,
  'Checks Passed':len(checks),'Rejected Demo Records':len(rejected),'Run Seconds':round(time.perf_counter()-started,3),
  'Clean File Hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((output/'clean').glob('*.csv'))},
  'Timing Scope':'Cleaning, checks, SQL database and base report extracts. Excludes export retrieval, human review, additional scenario calculations, dashboard publication and delivery. Manual baseline not measured.'}
 (output/'refresh_log.json').write_text(json.dumps(result,indent=2))
 print(json.dumps({k:v for k,v in result.items() if k not in ['Tables','Clean File Hashes']},indent=2)); return result

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('--input',type=Path,default=BASE/'raw'); p.add_argument('--output',type=Path,default=BASE/'processed'); a=p.parse_args(); refresh(a.input,a.output)
