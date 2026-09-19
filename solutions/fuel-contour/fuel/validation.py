"""Schema plus semantic input errors (as opposed to feasible-domain violations)."""
import math
from .io import schema_validate

class InputError(ValueError):
    pass

def number(v, path, minimum=0):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < minimum:
        raise InputError(f'INVALID_NUMBER path={path} actual={v!r} minimum={minimum}')

def integer(v, path, minimum=-10000):
    number(v, path, minimum)
    if int(v) != v:
        raise InputError(f'INTEGER_REQUIRED path={path}')

def validate_plan(case, plan):
    schema_validate(plan, 'plan')
    years = {x['year'] for x in case['demand']}
    sources = {x['source_id'] for x in case['supply_sources']}
    options = {x['investment_id'] for x in case['investment_options']}
    d = plan['decisions']
    for section, field in [('supply_orders', 'ordered_volume_t'), ('capacity_reservations', 'reserved_capacity_t')]:
        seen = set()
        for r in d[section]:
            for key in ['source_id', 'year', field, 'start_day', 'end_day']:
                if key not in r:
                    raise InputError(f'MISSING_FIELD {section}.{key}')
            number(r[field], f'{section}.{field}')
            if r['source_id'] not in sources:
                raise InputError(f'UNKNOWN_SOURCE {r["source_id"]}')
            if r['year'] not in years:
                raise InputError(f'UNKNOWN_YEAR {r["year"]}')
            key = (r['source_id'], r['year'])
            if key in seen:
                raise InputError(f'DUPLICATE_CONTRACT {key}')
            seen.add(key)
            for k in ['start_day', 'end_day']:
                integer(r[k], k, 1)
            if not 1 <= r['start_day'] <= r['end_day'] <= 365:
                raise InputError('INVALID_PERIOD expected=1..365')
            if section == 'supply_orders':
                integer(r.get('order_day'), 'order_day')
    seen = set()
    for r in d['investments']:
        if r.get('investment_id') not in options or r['investment_id'] in seen:
            raise InputError('UNKNOWN_OR_DUPLICATE_INVESTMENT')
        seen.add(r['investment_id'])
        integer(r.get('decision_day'), 'decision_day', 0)
        integer(r.get('commission_day'), 'commission_day', 0)
        if r['commission_day'] < r['decision_day']:
            raise InputError('COMMISSION_BEFORE_DECISION')
    policy = d['inventory_policy']
    number(policy.get('opening_stock_t'), 'opening_stock_t')
    if policy.get('opening_source_id') not in sources:
        raise InputError('OPENING_SOURCE_REQUIRED')
    if policy.get('allocation') != 'critical_first':
        raise InputError('UNSUPPORTED_ALLOCATION expected=critical_first')
    if plan.get('assumptions', {}).get('timing') != '365-day-year;month=365/12;upper-lead;ceil':
        raise InputError('TIMING_ASSUMPTION_REQUIRED')

def validate_scenario(case, scenario):
    schema_validate(scenario, 'scenario')
    names = {s['name'] for s in case['supply_sources']}
    years = {str(d['year']) for d in case['demand']}
    for section in ['demand_multiplier', 'critical_demand_multiplier', 'variable_price_multiplier', 'actual_delivery_share']:
        for key, val in scenario.get(section, {}).items():
            if isinstance(val, dict):
                if key not in names:
                    raise InputError(f'UNKNOWN_SCENARIO_SOURCE {key}')
                for year, x in val.items():
                    if str(year) not in years and year != 'default':
                        raise InputError(f'UNKNOWN_SCENARIO_YEAR {year}')
                    number(x, f'{section}.{key}.{year}')
                    if section == 'actual_delivery_share' and x > 1:
                        raise InputError('DELIVERY_SHARE_ABOVE_ONE')
            else:
                if str(key) not in years and key != 'default':
                    raise InputError(f'UNKNOWN_SCENARIO_KEY {key}')
                number(val, f'{section}.{key}')
                if section == 'actual_delivery_share' and val > 1:
                    raise InputError('DELIVERY_SHARE_ABOVE_ONE')
