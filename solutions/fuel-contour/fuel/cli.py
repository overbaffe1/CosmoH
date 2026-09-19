import argparse
import json
from pathlib import Path
from .io import ROOT, load_case, load_scenario, load_json, save_json, export_result, digest
from .engine import evaluate
from .planning import make_plan
from .analysis import sensitivity, risk_analysis, monte_carlo, mcda, extension_demo


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
        for result in [base, stress]:
            export_result(result, output / strategy / result['scenario_id'])
        sens = sensitivity(case, plan)
        mc = monte_carlo(case, plan, count=count)
        ext = extension_demo(case, plan)
        save_json(output / strategy / 'sensitivity.json', sens)
        save_json(output / strategy / 'monte_carlo.json', mc)
        save_json(output / strategy / 'extension.json', ext)
        summaries[strategy] = dict(plan_id=plan['plan_id'], base=base['summary'], stress=stress['summary'],
                                   yearly_base=base['yearly_balance'], yearly_stress=stress['yearly_balance'],
                                   costs_base=base['financial_breakdown'], risks=base['risk_register'],
                                   sensitivity=sens, monte_carlo={k:v for k,v in mc.items() if k!='runs'})
        alternatives.append({'plan_id': plan['plan_id'], 'base': base['summary'], 'stress': stress['summary']})
    report = {'case_version': case['version'], 'status': 'TEAM_ANALYSIS', 'strategies': summaries, 'mcda': mcda(alternatives)}
    save_json(output / 'summary.json', report)
    print(json.dumps({k: {s:v[s] for s in ['base','stress']} for k,v in summaries.items()}, ensure_ascii=False, indent=2))
    print(f'Reproducibility SHA256: {digest(report)}')
    return report


def main():
    parser = argparse.ArgumentParser(description='Fuel contour 2035: deterministic scenario planner')
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init'); init.add_argument('--strategy', choices=['earth','lunar'], default='earth'); init.add_argument('--output', required=True)
    run = sub.add_parser('run'); run.add_argument('--plan', required=True); run.add_argument('--scenario', choices=['BASE','MANDATORY_STRESS'], default='BASE'); run.add_argument('--output', required=True)
    allruns = sub.add_parser('suite'); allruns.add_argument('--output', default=str(ROOT/'results')); allruns.add_argument('--mc-count', type=int, default=100)
    a = parser.parse_args()
    if a.command == 'init':
        save_json(a.output, make_plan(load_case(), a.strategy))
    elif a.command == 'run':
        result = evaluate(load_case(), load_json(a.plan), load_scenario(a.scenario))
        export_result(result, a.output)
        print(json.dumps(result['summary'], indent=2))
    else:
        suite(a.output, a.mc_count)

if __name__ == '__main__':
    main()
