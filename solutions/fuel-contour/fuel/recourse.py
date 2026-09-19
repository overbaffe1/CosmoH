"""Restricted post-observation response, not a universal adaptive optimizer.

All baseline contracts, future orders, investments and opening stock remain locked.
Only a new, previously unused Emergency source-year contract may be appended.
"""
import copy
from .engine import evaluate, lead_days
from .validation import InputError, integer, number, validate_plan


def emergency_response(case, plan, event_year=2038, delivery_share=0., observed_after_days=0,
                       max_emergency_t=80.):
    validate_plan(case, plan)
    integer(event_year, 'event_year', 0)
    integer(observed_after_days, 'observed_after_days', 0)
    number(delivery_share, 'delivery_share')
    number(max_emergency_t, 'max_emergency_t')
    years = sorted(r['year'] for r in case['demand'])
    if event_year not in years or event_year < 2038:
        raise InputError('RECOURSE_YEAR: select a horizon year from 2038')
    if observed_after_days > 364 or delivery_share > 1:
        raise InputError('RECOURSE_RANGE: delay 0..364 days; delivery share 0..1')
    sources = {s['source_id']: s for s in case['supply_sources']}
    if not {'D', 'E'} <= sources.keys():
        raise InputError('RECOURSE_REQUIRES_D_AND_E')
    lunar, emergency = sources['D'], sources['E']
    scenario = {'scenario_id': 'TEAM_OBSERVED_LUNAR_OUTAGE', 'status': 'TEAM_ASSUMPTION',
                'actual_delivery_share': {lunar['name']: {event_year: delivery_share}},
                'notes': ['Separate annual Lunar disruption, not mandatory stress.',
                          'At observation the remaining annual delivery fraction is announced; no probabilistic forecast.',
                          'Emergency spare capacity can be contracted then at control tariff; availability is a TEAM assumption.']}
    offset = (event_year-years[0])*365
    observed_day = offset+observed_after_days
    lead = lead_days(emergency)
    arrival_day = observed_day+lead
    start_day = observed_after_days+lead+1
    original = copy.deepcopy(plan)
    orders = plan['decisions']['supply_orders']
    lunar_order = next((r for r in orders if r['source_id']=='D' and r['year']==event_year), None)
    remaining_loss = 0.
    if lunar_order:
        remaining_days = max(0, lunar_order['end_day']-max(lunar_order['start_day'], observed_after_days+1)+1)
        remaining_loss = lunar_order['ordered_volume_t']*(1-delivery_share)*remaining_days/(lunar_order['end_day']-lunar_order['start_day']+1)
    existing = any(r['source_id']=='E' and r['year']==event_year
                   for section in ('supply_orders', 'capacity_reservations') for r in plan['decisions'][section])
    available_t = emergency['capacity_t_per_year']*max(0,365-start_day+1)/365
    quantity = min(remaining_loss, available_t, max_emergency_t)
    action = 'ordered'
    if remaining_loss <= 1e-8:
        action = 'no_remaining_exposure'
    elif existing:
        action = 'blocked_existing_emergency_contract'
    elif start_day > 365:
        action = 'too_late_this_year'
    elif quantity <= 1e-8:
        action = 'zero_purchase_limit'
    adapted = copy.deepcopy(plan)
    if action == 'ordered':
        fraction = (365-start_day+1)/365
        adapted['plan_id'] += '_POST_OBSERVATION_E'
        adapted['scenario_id'] = scenario['scenario_id']
        adapted['decisions']['supply_orders'].append(dict(source_id='E', year=event_year,
            ordered_volume_t=quantity, start_day=start_day, end_day=365, order_day=observed_day))
        adapted['decisions']['capacity_reservations'].append(dict(source_id='E', year=event_year,
            reserved_capacity_t=quantity/fraction, start_day=start_day, end_day=365))
        adapted['assumptions']['post_observation_response'] = {
            'status': 'TEAM_ASSUMPTION', 'observed_day': observed_day, 'arrival_day': arrival_day,
            'reservation_decision_day': observed_day,
            'policy': 'Buy min(announced remaining lost gross volume, prorated E capacity, purchase limit); no future-result optimization',
            'locked': 'All original orders/reservations/investments/opening stock, including future-dated commitments',
            'commercial_terms': 'New spare E contract available at observation at control tariff; not an organizer guarantee'}
    else:
        quantity = 0.
    before = evaluate(case, plan, scenario)
    after = evaluate(case, adapted, scenario)
    prefix_equal = all(a == b for a,b in zip(before['inventory_trace'], after['inventory_trace'])
                       if (a['year']-years[0])*365+a['day']-1 < arrival_day)
    if not prefix_equal:
        raise AssertionError('RECOURSE_CHANGED_PHYSICAL_HISTORY')
    assert plan == original
    return {'status': 'TEAM_ASSUMPTION', 'scenario': scenario, 'action': action,
            'event_year': event_year, 'observed_after_days': observed_after_days,
            'observed_day': observed_day, 'first_possible_arrival_day': arrival_day,
            'lead_time_days': lead, 'remaining_lost_gross_t': remaining_loss,
            'available_emergency_t': available_t, 'added_order_t': quantity,
            'prefix_unchanged_until_arrival': prefix_equal,
            'original_commitments_unchanged': all(adapted['decisions'][key][:len(plan['decisions'][key])]==plan['decisions'][key]
                for key in ('supply_orders','capacity_reservations','investments')) and adapted['decisions']['inventory_policy']==plan['decisions']['inventory_policy'],
            'incremental_cost_mln': after['summary']['total_cost_mln']-before['summary']['total_cost_mln'],
            'avoided_shortage_t': before['summary']['shortage_t']-after['summary']['shortage_t'],
            'residual_failed_rules': [r for r in after['constraint_checks'] if not r['passed']],
            'limitations': ['Annual disruption starts on day one; later observation is an information delay, not a shifted event.',
                           'New Emergency contract only; existing source-year contracts are never resized.',
                           'No lost service before arrival can be undone; reserve or service failures can remain.',
                           'All original future orders are locked too; this is deliberately more restrictive than full recourse.',
                           'Not combined with mandatory stress, not a policy proven feasible in every scenario.'],
            'input_plan': original, 'response_plan': adapted, 'before': before, 'after': after}
