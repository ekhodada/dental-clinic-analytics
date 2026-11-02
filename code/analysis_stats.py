"""I compare booking no-show proportions using the Python standard library."""
import math


# I calculate a pooled, two-sided z-test for two observed proportions.
def two_proportion_z_test(events_a, total_a, events_b, total_b):
    if total_a <= 0 or total_b <= 0:
        raise ValueError('Both groups need eligible appointments.')
    if not 0 <= events_a <= total_a or not 0 <= events_b <= total_b:
        raise ValueError('Event counts must fall within their group totals.')
    pooled_rate = (events_a + events_b) / (total_a + total_b)
    standard_error = math.sqrt(pooled_rate * (1 - pooled_rate) * (1 / total_a + 1 / total_b))
    z_score = (events_a / total_a - events_b / total_b) / standard_error if standard_error else 0.0
    p_value = math.erfc(abs(z_score) / math.sqrt(2))
    return {'z_score': z_score, 'p_value': p_value}


# I compare Maple with Harbour using completed and no-show appointments from 2025.
def branch_noshow_test(connection):
    query = '''SELECT branch,SUM(no_shows),SUM(eligible_appointments)
        FROM noshow_by_lead_time WHERE branch IN ('Maple','Harbour') GROUP BY branch'''
    groups = {branch: {'no_shows': missed, 'eligible_appointments': total,
                     'no_show_rate': missed / total}
              for branch, missed, total in connection.execute(query)}
    maple, harbour = groups['Maple'], groups['Harbour']
    result = two_proportion_z_test(maple['no_shows'], maple['eligible_appointments'],
                                   harbour['no_shows'], harbour['eligible_appointments'])
    return {'year': 2025, 'comparison': 'Maple minus Harbour', 'alternative': 'two-sided',
            'groups': groups, **result,
            'rate_difference_percentage_points': 100 * (maple['no_show_rate'] - harbour['no_show_rate'])}
