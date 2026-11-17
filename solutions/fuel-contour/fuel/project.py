"""A full auditable project, using the same pure kernel as every other entry point."""
from .engine import evaluate
from .analysis import risk_analysis
from .io import load_scenario


def calculate_project(case, plan, scenario):
    result = evaluate(case, plan, scenario)
    base = result if scenario['scenario_id']=='BASE' else evaluate(case, plan, load_scenario('BASE'), trace=False)
    stress = result if scenario['scenario_id']=='MANDATORY_STRESS' else evaluate(case, plan, load_scenario('MANDATORY_STRESS'), trace=False)
    result['risk_register'] = risk_analysis(case, plan, base)
    result['scenario_comparison'] = [{'scenario_id': r['scenario_id'], 'plan_id': plan['plan_id'], **r['summary']} for r in (base, stress)]
    if scenario['scenario_id'] not in ('BASE', 'MANDATORY_STRESS'):
        result['scenario_comparison'].append({'scenario_id': scenario['scenario_id'], 'plan_id': plan['plan_id'], **result['summary']})
    # Research copies cannot be passed off as control runs, even in comparison labels.
    if case.get('status')=='TEAM_ASSUMPTION':
        for row in result['scenario_comparison']:
            row['environment_template'] = row['scenario_id']
            row['scenario_id'] = 'TEAM_COPY_'+row['scenario_id']
    return result
