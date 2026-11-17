"""Research copies; control constraints and source files are never rewritten."""
import copy
from .io import digest, schema_validate
from .validation import InputError, number


def research_copy(original, patch):
    if not isinstance(patch, dict) or set(patch)-{'demand', 'supply_sources', 'basis'}:
        raise InputError('RESEARCH_COPY supports demand, supply_sources and basis only')
    if not isinstance(patch.get('basis'), str) or not patch['basis'].strip():
        raise InputError('RESEARCH_COPY_BASIS_REQUIRED')
    case = copy.deepcopy(original)
    changes = []
    for table, key, schema in [('demand', 'year', 'demand'), ('supply_sources', 'source_id', 'supply_sources')]:
        if table not in patch:
            continue
        rows = patch[table]
        if not isinstance(rows, list) or not 1 <= len(rows) <= (20 if table=='demand' else 30):
            raise InputError(f'RESEARCH_COPY_SIZE {table}')
        seen, names = set(), set()
        old = {r[key]: r for r in original[table]}
        converted = []
        for row in rows:
            check = copy.deepcopy(row)
            check['status'] = 'CASE_INPUT'  # Organizer shape; exported changed rows are TEAM_ASSUMPTION.
            schema_validate(check, schema)
            for k, v in check.items():
                if isinstance(v, (float, int)):
                    number(v, f'{table}.{k}')
            ident = check[key]
            if ident in seen:
                raise InputError(f'DUPLICATE_CASE_ROW {table}.{ident}')
            seen.add(ident)
            if table == 'demand' and check['base_critical_t'] > check['base_total_t']:
                raise InputError(f'CRITICAL_EXCEEDS_TOTAL year={ident}')
            if table == 'supply_sources':
                if check['name'] in names:
                    raise InputError('DUPLICATE_SOURCE_NAME')
                names.add(check['name'])
                if check['lead_time_min_value'] > check['lead_time_max_value']:
                    raise InputError('LEAD_RANGE_INVERTED')
            if old.get(ident) != check:
                changes.append({'table': table, 'key': ident, 'before': old.get(ident), 'after': copy.deepcopy(check)})
                check['status'] = 'TEAM_ASSUMPTION'
            converted.append(check)
        if not old.keys() <= seen:
            raise InputError(f'CONTROL_ROWS_CANNOT_BE_REMOVED {table}')
        case[table] = converted
    years = sorted(r['year'] for r in case['demand'])
    if years != list(range(years[0], years[-1]+1)):
        raise InputError('NONCONTIGUOUS_YEARS')
    case['version'] += '+TEAM_COPY'
    case['status'] = 'TEAM_ASSUMPTION'
    case['research_provenance'] = {'baseline_case_sha256': digest(original), 'basis': patch['basis'], 'changes': changes,
                                 'constraints': 'Original control limits and their original end dates retained; annual service/reserve continue in research years'}
    return case
