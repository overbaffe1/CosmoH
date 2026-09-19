import argparse
import json
from pathlib import Path
from .io import ROOT, load_case, load_scenario, load_json, save_json, export_result, export_table, digest
from .engine import evaluate
from .planning import make_plan
from .analysis import sensitivity, risk_analysis, monte_carlo, mcda, extension_demo, compare_decisions, parameter_sensitivity, stress_attribution, price_crossover
from .project import calculate_project
from .decision import discount_rate_crossover, decision_brief


def suite(output, count=100):
    case = load_case()
    output = Path(output)
    summaries, alternatives = {}, []
    for strategy in ['earth', 'lunar']:
        plan = make_plan(case, strategy)
        save_json(output / strategy / 'plan.json', plan)
        reopened = load_json(output / strategy / 'plan.json')
        assert plan == reopened
        base = evaluate(case, reopened, load_scenario('BASE'))
        assert base == evaluate(case, plan, load_scenario('BASE'))
        base['risk_register'] = risk_analysis(case, plan, base)
        stress = evaluate(case, plan, load_scenario('MANDATORY_STRESS'))
        comparison_rows = [{'scenario_id': r['scenario_id'], 'plan_id': plan['plan_id'], **r['summary']} for r in [base, stress]]
        base['scenario_comparison'] = comparison_rows
        stress['scenario_comparison'] = comparison_rows
        stress['risk_register'] = base['risk_register']
        for result in [base, stress]:
            export_result(result, output / strategy / result['scenario_id'])
        sens = sensitivity(case, plan)
        mc = monte_carlo(case, plan, count=count)
        ext = extension_demo(case, plan)
        stress_plan = make_plan(case, strategy, load_scenario('MANDATORY_STRESS'))
        save_json(output / strategy / 'stress_plan.json', stress_plan)
        planned = calculate_project(case, stress_plan, load_scenario('MANDATORY_STRESS'))
        export_result(planned, output / strategy / 'PLANNED_STRESS')
        comparison = compare_decisions(case, plan, stress_plan, load_scenario('BASE'), load_scenario('MANDATORY_STRESS'))
        save_json(output / strategy / 'decision_comparison.json', comparison)
        export_table(output / strategy / 'decision_comparison.csv', comparison['matrix'])
        export_table(output / strategy / 'decision_changes.csv', comparison['changes'])
        params = parameter_sensitivity(case, plan)
        attribution = stress_attribution(case, plan, load_scenario('MANDATORY_STRESS'))
        correlated = monte_carlo(case, plan, count=count, dependence='common_year')
        save_json(output / strategy / 'parameter_sensitivity.json', params)
        save_json(output / strategy / 'stress_attribution.json', attribution)
        save_json(output / strategy / 'monte_carlo_common_year.json', correlated)
        export_table(output / strategy / 'parameter_sensitivity.csv', params['points'])
        export_table(output / strategy / 'stress_attribution.csv', attribution['steps'])
        save_json(output / strategy / 'sensitivity.json', sens)
        save_json(output / strategy / 'monte_carlo.json', mc)
        save_json(output / strategy / 'extension.json', ext)
        summaries[strategy] = dict(plan_id=plan['plan_id'], base=base['summary'], stress=stress['summary'],
                                   yearly_base=base['yearly_balance'], yearly_stress=stress['yearly_balance'],
                                   costs_base=base['financial_breakdown'], risks=base['risk_register'],
                                   sensitivity=sens, parameter_sensitivity=params, stress_attribution=attribution,
                                   planned_stress=planned['summary'], yearly_planned_stress=planned['yearly_balance'],
                                   costs_planned_stress=planned['financial_breakdown'], decision_comparison=comparison,
                                   roadmap=base['roadmap'], roadmap_planned_stress=planned['roadmap'],
                                   monte_carlo_common_year={k:v for k,v in correlated.items() if k!='runs'},
                                   monte_carlo={k:v for k,v in mc.items() if k!='runs'})
        alternatives.append({'plan_id': plan['plan_id'], 'base': base['summary'], 'stress': stress['summary']})
    report = {'case_version': case['version'], 'status': 'TEAM_ANALYSIS', 'strategies': summaries, 'mcda': mcda(alternatives),
              'price_crossover': price_crossover(case, make_plan(case, 'lunar'), make_plan(case, 'earth')),
              'planned_stress_mcda': mcda([{'plan_id': v['plan_id']+' + EX_ANTE_STRESS_DESIGN', 'base': v['base'], 'stress': v['planned_stress']} for v in summaries.values()])}
    report['discount_rate_crossover'] = discount_rate_crossover(summaries['earth']['costs_base'], summaries['lunar']['costs_base'])
    save_json(output / 'decision_brief.json', decision_brief(report))
    save_json(output / 'summary.json', report)
    export_table(output / 'comparison.csv', [{'strategy': k, 'scenario_design': tag, 'money_unit': 'mln constant-2035 units', 'mass_unit': 't', **v[tag]} for k, v in summaries.items() for tag in ['base','stress','planned_stress']])
    print(json.dumps({k: {s:v[s] for s in ['base','stress','planned_stress']} for k,v in summaries.items()}, ensure_ascii=False, indent=2))
    print(f'Reproducibility SHA256: {digest(report)}')
    return report


def main():
    parser = argparse.ArgumentParser(description='Fuel contour 2035: deterministic scenario planner')
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init'); init.add_argument('--strategy', choices=['earth','lunar'], default='earth'); init.add_argument('--output', required=True); init.add_argument('--design-scenario', choices=['BASE','MANDATORY_STRESS'], default='BASE')
    run = sub.add_parser('run'); run.add_argument('--plan', required=True); run.add_argument('--scenario', choices=['BASE','MANDATORY_STRESS'], default='BASE'); run.add_argument('--output', required=True)
    allruns = sub.add_parser('suite'); allruns.add_argument('--output', default=str(ROOT/'results')); allruns.add_argument('--mc-count', type=int, default=100)
    a = parser.parse_args()
    if a.command == 'init':
        save_json(a.output, make_plan(load_case(), a.strategy, load_scenario(a.design_scenario)))
    elif a.command == 'run':
        result = calculate_project(load_case(), load_json(a.plan), load_scenario(a.scenario))
        export_result(result, a.output)
        print(json.dumps(result['summary'], indent=2))
    else:
        suite(a.output, a.mc_count)

if __name__ == '__main__':
    main()
