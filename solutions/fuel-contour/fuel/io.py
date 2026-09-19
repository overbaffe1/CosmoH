import csv
import hashlib
import json
from pathlib import Path
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'vendor/test_oil'

def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

SCHEMAS = {p.name.split('.')[0]: json.loads(p.read_text(encoding='utf-8')) for p in (REFERENCE / 'schemas').glob('*.json')}

def schema_validate(value, name):
    Draft202012Validator(SCHEMAS[name]).validate(value)

def load_case():
    tables = {}
    for name in ['demand', 'supply_sources', 'storage_options', 'investment_options', 'constraints']:
        with (REFERENCE / f'data/{name}.csv').open(encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            for k, v in row.items():
                if k in ('year', 'available_from_year'):
                    row[k] = int(v) if v else None
                elif k.endswith(('_t', '_year', '_mln', '_per_t', '_capacity', '_share', '_value', '_throughput')) or k == 'value':
                    try:
                        row[k] = float(v)
                    except ValueError:
                        pass
        tables[name] = rows
    for row in tables['demand']:
        schema_validate(row, 'demand')
    for row in tables['supply_sources']:
        schema_validate(row, 'supply_sources')
    tables['version'] = 'cec6de1950276091689e71a67f9a875fb4ca6213'
    return tables

def load_scenario(name):
    paths = {'BASE': 'base', 'MANDATORY_STRESS': 'mandatory_stress'}
    value = yaml.safe_load((REFERENCE / f'scenarios/{paths[name]}.yaml').read_text())
    schema_validate(value, 'scenario')
    return value

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()

def export_result(result, directory):
    directory = Path(directory)
    schema_validate(result, 'export')
    save_json(directory / 'result.json', result)
    for key in ('yearly_balance', 'source_schedule', 'inventory_trace', 'financial_breakdown', 'constraint_checks', 'risk_register', 'pre_horizon', 'summary'):
        rows = result[key]
        if isinstance(rows, dict):
            rows = [rows]
        if not rows:
            rows = [{'status': 'empty'}]
        metadata = {'scenario_id': result['scenario_id'], 'plan_id': result['plan_id'], 'assumptions_reference': 'result.json#assumptions_reference', 'units': json.dumps(result['units'], ensure_ascii=False)}
        rows = [{**metadata, **{k: json.dumps(v, ensure_ascii=False, allow_nan=False) if isinstance(v, (dict, list)) else v for k, v in r.items()}} for r in rows]
        fields = list(dict.fromkeys(k for r in rows for k in r))
        with (directory / f'{key}.csv').open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
