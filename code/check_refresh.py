"""Repeatability and rejection-gate tests. Run with --work pointing to a scratch folder."""
import json,csv,shutil,hashlib,contextlib,io,argparse
from pathlib import Path
from clean_and_refresh import BASE,refresh,read,write

def main(work):
 output=work/'results'; source=work/'raw'; source.parent.mkdir(parents=True,exist_ok=True)
 shutil.copytree(BASE/'raw',source,dirs_exist_ok=True)
 with contextlib.redirect_stdout(io.StringIO()):
  a=refresh(source,output); b=refresh(source,output)
 assert a['Clean File Hashes']==b['Clean File Hashes']
 expected=json.loads((BASE/'settings.json').read_text())['expected_rows']
 assert all(a['Tables'][name]['Clean Rows']==count for name,count in expected.items())
 assert sum(t['Duplicate Rows Removed'] for t in a['Tables'].values())==100
 assert a['Rejected Demo Records']==6
 db=output/'dental_clinic.sqlite'; before=hashlib.sha256(db.read_bytes()).hexdigest()
 fields,rows=read(source/'payments.csv'); bad=dict(rows[0]); bad['Payment ID']='UNEXPECTED'; bad['Invoice ID']='MISSING'; rows.append(bad); write(source/'payments.csv',rows,fields)
 blocked=False
 try:
  with contextlib.redirect_stdout(io.StringIO()): refresh(source,output)
 except ValueError: blocked=True
 assert blocked and hashlib.sha256(db.read_bytes()).hexdigest()==before
 result={'Same inputs produce identical clean files':True,'All expected row counts match':True,
  '100 duplicate rows removed':True,'Six demo errors isolated':True,
  'New invalid payment blocks publication':True,'Prior published database preserved':True,
  'Measured run seconds':[a['Run Seconds'],b['Run Seconds']]}
 (BASE/'processed'/'repeatability_checks.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(); p.add_argument('--work',type=Path,required=True); main(p.parse_args().work)
