"""Pure decision evidence: feasible-first comparisons, not an optimizer or preference oracle."""
import math
from .validation import InputError


def discount_rate_crossover(earth_flows, lunar_flows, low=0., high=.1):
    """Find one bracketed PV equality, using the kernel's first-year preparation recognition.

    Interval is a TEAM research choice, not a forecast of market interest rates.
    No uniqueness or global optimality claim. The input cash flows are never mutated.
    """
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
           for x in (low, high)) or not 0 <= low < high <= 1:
        raise InputError('RATE_SEARCH_RANGE: require 0 <= low < high <= 1')
    years = [r['year'] for r in earth_flows]
    if not years or years != [r['year'] for r in lunar_flows] or years != sorted(set(years)):
        raise InputError('CASHFLOW_YEARS_MISMATCH')
    for row in earth_flows + lunar_flows:
        value = row['total_mln']
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise InputError('CASHFLOW_COST_INVALID')
    def pv(rows, rate):
        return sum(r['total_mln']/(1+rate)**(r['year']-years[0]+1) for r in rows)
    def gap(rate):
        return pv(lunar_flows, rate)-pv(earth_flows, rate)
    result = {'status': 'TEAM_ASSUMPTION', 'unit': 'real annual share',
              'search_interval': [low, high], 'difference': 'PV Lunar minus PV Earth, mln constant-2035 units',
              'convention': 'End-year cashflows to start of first year; preparation already included in first year',
              'basis': 'Research interval; fixed cashflows and unchanged physical feasibility, no market forecast',
              'samples': [{'rate': r, 'earth_pv_mln': pv(earth_flows, r),
                           'lunar_pv_mln': pv(lunar_flows, r), 'lunar_minus_earth_mln': gap(r)}
                          for r in (low, (low+high)/2, high)], 'bracket': None}
    a, b = low, high
    if all(e['total_mln'] == l['total_mln'] for e, l in zip(earth_flows, lunar_flows)):
        result['status_detail'] = 'identical_cashflows'
    elif gap(a) == 0 or gap(b) == 0:
        root = a if gap(a) == 0 else b
        result.update(status_detail='endpoint_equality', bracket=[root, root])
    elif gap(a)*gap(b) > 0:
        result['status_detail'] = 'not_bracketed'  # Does not prove no internal roots.
    else:
        for _ in range(40):
            mid = (a+b)/2
            if gap(a)*gap(mid) <= 0:
                b = mid
            else:
                a = mid
        result.update(status_detail='bracketed', bracket=[a, b])
    return result


def decision_brief(summary):
    """Extract traceable facts. No weighted average makes an infeasible plan admissible."""
    strategies = summary['strategies']
    matrix = [{**r, 'architecture': key} for key, value in strategies.items()
              for r in value['decision_comparison']['matrix']]
    if len({r['discount_rate'] for r in matrix}) != 1:
        raise InputError('DISCOUNT_BASIS_MISMATCH')
    choices = {}
    for environment in ('BASE', 'MANDATORY_STRESS'):
        passing = [r for r in matrix if r['scenario_id'] == environment and r['violations'] == 0]
        passing.sort(key=lambda r: r['discounted_cost_mln'])
        choices[environment] = {
            'rule': 'Among evaluated feasible plans only, minimize discounted cost at one common rate',
            'ranked_feasible_candidates': passing,
            'economic_candidate': passing[0] if passing else None,
            'limitation': 'Conditional economic preference, not global optimum or automatic investment approval'}
    joint = []
    for key, value in strategies.items():
        for role in ('baseline', 'redesign'):
            rows = [r for r in value['decision_comparison']['matrix'] if r['plan_role'] == role]
            if {r['scenario_id'] for r in rows} == {'BASE', 'MANDATORY_STRESS'} and all(r['violations'] == 0 for r in rows):
                joint.append({'architecture': key, 'plan_role': role})
    return {'status': 'TEAM_ANALYSIS', 'choices': choices, 'fixed_plans_feasible_in_both': joint,
            'warning': 'Switching between scenario-specific plans is not an implementable adaptive policy; respect dated commitments',
            'rate_crossover': summary['discount_rate_crossover'],
            'stress_explanation': {key: value['stress_attribution'] for key, value in strategies.items()},
            'stakeholders': {key: value['decision_comparison']['stakeholders'] for key, value in strategies.items()}}
