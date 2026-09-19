"""Transparent heuristic initial plans, not an optimizer or organizer recommendation."""
from .engine import lead_days, reserve_required

ASSUMPTIONS = {
    'status': 'TEAM_ASSUMPTION',
    'timing': '365-day-year;month=365/12;upper-lead;ceil',
    'delivery': 'Uniform daily arrivals in decision window, before uniform daily demand',
    'contracts': 'One annual contract/source; reservation and TOP prorated by contract window',
    'holding': 'Exact within-day integral with uniform demand; no stock below zero',
    'opening_stock': 'Existing Earth channel available pre-horizon; separate paid 2034 contract arrives day -1',
    'unfulfilled_orders': 'Ordered fuel remains payable; no refund/mission penalties assumed',
    'overflow': 'Reject gross delivery before acceptance, record violation; ordered amount remains payable',
    'emergency_base': 'Conservative: any positive scheduled Emergency order counts as a base-channel year',
    'zbo_commissioning': 'Same day as full payment, not before 2036; construction duration unspecified',
    'earth_new': 'Option fee and exercise paid together; preparation and order lead run concurrently',
    'lunar': 'First delivery at commission + upper lead; pre-commission orders do not bypass this',
    'discount_rate': {'value': 0, 'unit': 'real annual share', 'basis': 'undiscounted comparison'},
    'zero_demand_service': 1,
    'initial_plan_policy': '20 t opening; next-year stress reserve + 8 t buffer; cheapest available first',
}

def make_plan(case, strategy='earth'):
    first = min(r['year'] for r in case['demand'])
    sources = {r['source_id']: r for r in case['supply_sources']}
    plan = {'plan_id': f'TEAM_{strategy.upper()}', 'scenario_id': 'BASE', 'status': 'TEAM_DECISION',
            'assumptions': dict(ASSUMPTIONS), 'decisions': {'supply_orders': [], 'capacity_reservations': [],
            'investments': [{'investment_id': 'EARTH_NEW', 'decision_day': 0, 'commission_day': 730},
                            {'investment_id': 'ZBO', 'decision_day': 365, 'commission_day': 365}],
            'inventory_policy': {'opening_stock_t': 20., 'opening_source_id': 'A', 'allocation': 'critical_first'}}}
    if strategy == 'lunar':
        plan['decisions']['investments'].append({'investment_id': 'LUNAR_ISRU', 'decision_day': 730, 'commission_day': 1095})
    previous = 20.
    demands = sorted(case['demand'], key=lambda r: r['year'])
    for idx, row in enumerate(demands):
        y = row['year']
        future = demands[min(idx+1, len(demands)-1)]
        target = reserve_required(future['base_total_t'] * (1.15 if future['year'] >= 2038 else 1)) + 8
        storage_id = 'BASE' if y == first else 'ZBO'
        loss = next(s['loss_rate_on_throughput'] for s in case['storage_options'] if s['storage_id'] == storage_id)
        needed = (row['base_total_t'] + target - previous)/(1-loss)
        previous = target
        priority = (['D'] if strategy == 'lunar' and y >= 2038 else []) + ['A'] + (['C'] if y >= 2037 else []) + ['B', 'E']
        for sid in priority:
            amount = min(needed, sources[sid]['capacity_t_per_year'])
            if amount <= 1e-8:
                continue
            needed -= amount
            start = 1 + lead_days(sources[sid]) if sid == 'D' and y == 2038 else 1
            # Delivery compressed into post-commissioning window, annual contract still full year.
            plan['decisions']['capacity_reservations'].append({'source_id': sid, 'year': y, 'reserved_capacity_t': amount, 'start_day': 1, 'end_day': 365})
            plan['decisions']['supply_orders'].append({'source_id': sid, 'year': y, 'ordered_volume_t': amount,
                                                     'start_day': start, 'end_day': 365,
                                                     'order_day': (y-first)*365+start-1-lead_days(sources[sid])})
    return plan
