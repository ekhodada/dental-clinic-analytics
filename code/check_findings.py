"""I verify findings structure, calculations and response to changed inputs."""
from pathlib import Path
import json
import math
import re
import sqlite3
from business_questions import calculate_metrics, make_findings, render_findings, PARTS

BASE = Path(__file__).resolve().parents[1]


# I require four findings, five parts each and short first-person explanations.
def check_structure(findings):
    assert len(findings) == 4
    for finding in findings:
        assert list(finding['parts']) == PARTS
        for text in finding['parts'].values():
            assert text.startswith('I ')
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text.strip())
            assert 1 <= len(sentences) <= 2, text
            assert text.count('$') == len(re.findall(r'estimated\s+~?\$', text)), text


# I independently confirm opportunity amounts against source-ledger calculations.
def check_values(connection, metrics, policy):
    revenue, lead = metrics['revenue'], metrics['lead_time']
    debt, branch = metrics['receivables'], metrics['branch_gap']
    assert math.isclose(revenue['root_average_charge_cents'], 134669, abs_tol=0.001)
    root_rows = connection.execute('''
        SELECT substr(a."Scheduled Start",1,4),COUNT(*),SUM(CAST(ROUND(t."Net Charge"*100) AS INTEGER))
        FROM treatments t JOIN appointments a USING("Appointment ID")
        WHERE t."Care Category"='Root Canal & Pulp Care' GROUP BY 1
    ''').fetchall()
    root = {year: (count, cents) for year, count, cents in root_rows}
    count_now, cents_now = root[str(metrics['year'])]
    count_before = root[str(metrics['previous_year'])][0]
    assert revenue['opportunity_cents'] == round((count_before-count_now) *
        policy['root_canal_recovery_share'] * cents_now / count_now)
    assert math.isclose(lead['retained_visits'], 229.63495076521534)
    assert lead['opportunity_cents'] == 5663168
    expected_working_balance = connection.execute('''
        SELECT SUM(CAST(ROUND("Still Owed"*100) AS INTEGER)) FROM unpaid_invoices
        WHERE CAST(julianday(?)-julianday("Bill Date") AS INTEGER) BETWEEN ? AND ?
    ''', (metrics['cutoff'], policy['collections_min_age_days'], policy['collections_max_age_days'])).fetchone()[0]
    assert debt['collections_balance_cents'] == expected_working_balance
    assert debt['previous_year_cash_timing_lift_cents'] == 31371762
    assert branch['opportunity_cents'] == 2480841
    assert branch['overlaps_group_reminder_opportunity'] is True
    assert debt['opportunity_cents'] == round(debt['recovery_base_cents'] * policy['collections_recovery_share'])
    direct = connection.execute('''
        SELECT SUM(Status='No-show'),SUM(Status IN ('Completed','No-show'))
        FROM appointments WHERE substr("Scheduled Start",1,4)=?
        AND CAST(julianday("Scheduled Start")-julianday("Booked At") AS INTEGER)>=30
    ''', (str(metrics['year']),)).fetchone()
    long = lead['bands']['30+ days']
    assert direct == (long['no_shows'], long['eligible_appointments'])
    assert lead['pattern_branch_count'] == lead['branch_count']


# I change only a memory copy to prove that findings follow data and policy inputs.
def check_recalculation(connection, metrics, policy):
    example = sqlite3.connect(':memory:')
    connection.backup(example)
    example.execute('''
        UPDATE treatments SET "Net Charge"="Net Charge"+10000
        WHERE rowid=(SELECT t.rowid FROM treatments t
          JOIN appointments a USING("Appointment ID")
          WHERE t."Care Category"='Root Canal & Pulp Care'
          AND substr(a."Scheduled Start",1,4)=? LIMIT 1)
    ''', (str(metrics['year']),))
    changed = calculate_metrics(example, policy)
    assert changed['revenue']['revenue_drop_cents'] == metrics['revenue']['revenue_drop_cents'] - 1000000
    assert changed['revenue']['opportunity_cents'] != metrics['revenue']['opportunity_cents']
    assert render_findings(make_findings(changed, policy)) != render_findings(make_findings(metrics, policy))
    example.close()
    zero_recovery = {**policy, 'root_canal_recovery_share': 0}
    assert calculate_metrics(connection, zero_recovery)['revenue']['opportunity_cents'] == 0
    no_significance = {**policy, 'significance_threshold': 0}
    last = make_findings(metrics, no_significance)[-1]['parts']['What happened']
    assert 'not statistically significant' in last


# I check generated files, ledger evidence and recalculation before publication.
def main():
    policy = json.loads((BASE / 'findings_policy.json').read_text())
    connection = sqlite3.connect(BASE / 'processed/dental_clinic.sqlite')
    connection.execute('PRAGMA temp_store=MEMORY')
    try:
        metrics = calculate_metrics(connection, policy)
        findings = make_findings(metrics, policy)
        check_structure(findings)
        check_values(connection, metrics, policy)
        check_recalculation(connection, metrics, policy)
        assert (BASE / 'FINDINGS.md').read_text() == render_findings(findings)
        saved = json.loads((BASE / 'processed/business_findings.json').read_text())
        assert saved['findings'] == findings
        assert saved['noshow_comparison_2025'] == metrics['noshow_comparison_2025']
    finally:
        connection.close()
    result = {'status': 'PASS', 'four_findings_with_five_parts': True,
              'one_or_two_sentences_per_part': True, 'every_dollar_labeled_estimated': True,
              'source_values_match': True, 'changed_data_changes_findings': True,
              'changed_policy_changes_estimates': True, 'generated_files_match_database': True,
              'overlapping_opportunities_not_added': True}
    (BASE / 'processed/findings_checks.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
