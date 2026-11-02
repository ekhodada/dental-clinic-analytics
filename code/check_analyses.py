"""I check the new reports against the ledger and small boundary examples."""
from pathlib import Path
import json
import math
import sqlite3
from analysis_stats import two_proportion_z_test, branch_noshow_test

BASE = Path(__file__).resolve().parents[1]


# I create a small database to test time, invoice-age and follow-up boundaries.
def example_database():
    db = sqlite3.connect(':memory:')
    db.executescript('''
    CREATE TABLE dates (Date TEXT);
    INSERT INTO dates VALUES ('2024-01-01'),('2025-12-31');
    CREATE TABLE locations ("Location ID" TEXT,"Location Name" TEXT);
    INSERT INTO locations VALUES ('L1','Harbour');
    CREATE TABLE patients ("Patient ID" TEXT,"First Visit" TEXT,"How They Found Us" TEXT);
    CREATE TABLE appointments ("Appointment ID" TEXT,"Patient ID" TEXT,"Location ID" TEXT,
      "Care Category" TEXT,Status TEXT,"Scheduled Start" TEXT,"Booked At" TEXT,
      "Treatment Started" TEXT,"Treatment Finished" TEXT);
    CREATE TABLE treatments ("Appointment ID" TEXT,"Invoice ID" TEXT,"Care Category" TEXT,"Net Charge" REAL);
    CREATE TABLE payments ("Invoice ID" TEXT,"Payment Date" TEXT,Amount REAL);
    ''')
    db.executescript((BASE/'code/reports.sql').read_text())
    return db


# I test age-band edges, duplicate service lines, missing history and incomplete follow-up.
def check_examples():
    db = example_database()
    from datetime import date, timedelta
    cutoff = date(2025,12,31)
    for age in [0,30,31,90,91,180,181,365,366]:
        day = (cutoff-timedelta(days=age)).isoformat()
        db.execute('INSERT INTO appointments VALUES (?,?,?,?,?,?,?,?,?)',
                   (str(age),'P','L1','Routine','Completed',day+'T09:00:00',day+'T08:00:00',day+'T09:00:00',day+'T10:00:00'))
        db.execute('INSERT INTO treatments VALUES (?,?,?,?)',(str(age),'I'+str(age),'Routine',100))
    db.execute("INSERT INTO payments VALUES ('I0','2026-01-01',100)")
    assert [r[0] for r in db.execute('SELECT unpaid_balance_cad FROM receivables_by_age')]==[200,200,200,200,100]
    db.execute("INSERT INTO treatments VALUES ('0','I0','Routine',50)")
    row = db.execute('SELECT net_revenue_cad,actual_treatment_hours FROM revenue_per_chair_hour').fetchone()
    assert row == (750.0,7.0)
    db.execute("DELETE FROM appointments")
    db.execute("DELETE FROM treatments")
    db.execute("DELETE FROM payments")
    people=[('P1','2024-02-29'),('P2','2025-07-01'),('P3','2020-01-01'),
            ('P4','2025-06-30'),('P5','2024-03-01'),('P6','2024-04-01')]
    db.executemany('INSERT INTO patients VALUES (?,?,?)',[(p,d,'Referral') for p,d in people])
    visits=[('A','P1','2024-02-29'),('B','P1','2025-02-28'),('C','P2','2025-07-01'),
            ('D','P3','2024-01-02'),('E','P4','2025-06-30'),('F','P5','2024-03-01'),
            ('G','P5','2024-03-01')]
    for visit,patient,day in visits:
        db.execute('INSERT INTO appointments VALUES (?,?,?,?,?,?,?,?,?)',
                   (visit,patient,'L1','Routine','Completed',day+'T09:00:00',day+'T08:00:00',day+'T09:00:00',day+'T10:00:00'))
        db.execute('INSERT INTO treatments VALUES (?,?,?,?)',(visit,visit,'Routine',100))
    result={r[0]:r[1:] for r in db.execute('SELECT patient_id,eligible_6_months,eligible_12_months,returned_12_months FROM patient_followup')}
    assert result['P1']==(1,1,1)
    assert result['P2'][:2]==(0,0)
    assert result['P3'][:2]==(0,0)
    assert result['P4'][:2]==(1,0)
    assert result['P5']==(1,1,0)
    assert result['P6'][:2]==(0,0)
    channel=db.execute('SELECT patients,eligible_12_month_patients,returned_12_month_patients FROM channel_value').fetchone()
    assert channel==(6,2,1)
    assert db.execute("SELECT return_rate_12_months FROM retention_cohorts WHERE first_visit_quarter='2025-Q3'").fetchone()[0] is None
    db.close()


# I verify report totals, the revenue bridge, statistical symmetry and expected results.
def main():
    db=sqlite3.connect(BASE/'processed/dental_clinic.sqlite')
    db.execute('PRAGMA temp_store=MEMORY')
    db.row_factory=sqlite3.Row
    bridge=[dict(r) for r in db.execute('SELECT * FROM revenue_bridge')]
    for row in bridge:
        difference=row['revenue_change_cad']-row['volume_effect_cad']-row['price_effect_cad']
        assert abs(difference)<0.011
    root=next(r for r in bridge if r['care_category']=='Root Canal & Pulp Care')
    assert (root['services_2024'],root['services_2025'])==(280,208)
    assert math.isclose(root['revenue_change_cad'],-95540.74,abs_tol=0.001)
    assert math.isclose(sum(r['revenue_change_cad'] for r in bridge),-172222.90,abs_tol=0.001)
    by_lead=[dict(r) for r in db.execute('''SELECT lead_time_band,SUM(no_shows) no_shows,
        SUM(eligible_appointments) eligible_appointments,
        1.0*SUM(no_shows)/SUM(eligible_appointments) no_show_rate
        FROM noshow_by_lead_time GROUP BY lead_time_band ORDER BY MIN(eligible_appointments)''')]
    expected={'0-6 days':(142,4746),'7-29 days':(390,8429),'30+ days':(457,4914)}
    assert all((r['no_shows'],r['eligible_appointments'])==expected[r['lead_time_band']] for r in by_lead)
    aging=[dict(r) for r in db.execute('SELECT * FROM receivables_by_age')]
    assert math.isclose(sum(r['unpaid_balance_cad'] for r in aging),633324.86,abs_tol=0.001)
    chairs=[dict(r) for r in db.execute('SELECT * FROM revenue_per_chair_hour')]
    assert math.isclose(sum(r['net_revenue_cad'] for r in chairs),4217135.70,abs_tol=0.001)
    actual_hours=db.execute('''SELECT SUM(ROUND((julianday("Treatment Finished")-
        julianday("Treatment Started"))*1440))/60.0 FROM appointments
        WHERE Status='Completed' AND substr("Scheduled Start",1,4)='2025' ''').fetchone()[0]
    assert math.isclose(sum(r['actual_treatment_hours'] for r in chairs),actual_hours,abs_tol=0.000001)
    assert db.execute('SELECT SUM(patients) FROM channel_value').fetchone()[0]==10000
    assert math.isclose(db.execute('SELECT SUM(net_revenue_cad) FROM channel_value').fetchone()[0],8606494.30,abs_tol=0.001)
    assert db.execute('SELECT SUM(patients) FROM retention_cohorts').fetchone()[0]==3936
    assert db.execute('''SELECT COUNT(*) FROM retention_cohorts WHERE
        returned_6_month_patients>eligible_6_month_patients OR
        returned_12_month_patients>eligible_12_month_patients OR
        (eligible_12_month_patients=0 AND return_rate_12_months IS NOT NULL)''').fetchone()[0]==0
    test=branch_noshow_test(db)
    assert test['groups']['Maple']['no_shows']==375 and test['groups']['Maple']['eligible_appointments']==5969
    assert test['groups']['Harbour']['no_shows']==282 and test['groups']['Harbour']['eligible_appointments']==6114
    reverse=two_proportion_z_test(282,6114,375,5969)
    assert reverse['z_score']==-test['z_score'] and reverse['p_value']==test['p_value']
    assert two_proportion_z_test(5,100,10,200)=={'z_score':0.0,'p_value':1.0}
    assert math.isclose(two_proportion_z_test(60,100,40,100)['z_score'],math.sqrt(8))
    check_examples()
    result={'status':'PASS','revenue_bridge_reconciles':True,'lead_time_counts_match':True,
        'aging_boundary_examples_pass':True,'no_future_receipts_counted':True,
        'chair_hours_count_each_visit_once':True,'cohort_windows_and_same_day_examples_pass':True,
        'channel_revenue_and_patient_totals_match':True,'statistical_symmetry_passes':True,
        'revenue_change_cad':round(sum(r['revenue_change_cad'] for r in bridge),2),
        'volume_effect_cad':round(sum(r['volume_effect_cad'] for r in bridge),2),
        'price_effect_cad':round(sum(r['price_effect_cad'] for r in bridge),2),
        'noshow_by_lead_time':by_lead,'noshow_comparison_2025':test}
    (BASE/'processed/analysis_checks.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    db.close()

if __name__=='__main__':
    main()
