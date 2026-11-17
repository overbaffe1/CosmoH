import copy
import json
import pytest
from jsonschema import ValidationError
from fuel.engine import evaluate, lead_days, contract_cost
from fuel.io import schema_validate, load_scenario, REFERENCE, load_json
from fuel.validation import InputError
from fuel.planning import make_plan


def failures(result):
    return [x for x in result['constraint_checks'] if not x['passed']]

@pytest.mark.parametrize('strategy', ['earth', 'lunar'])
def test_full_balance(case, base, strategy):
    plan = make_plan(case, strategy)
    result = evaluate(case, plan, base)
    assert failures(result) == []
    schema_validate(result, 'export')
    json.dumps(result, allow_nan=False)
    for r in result['inventory_trace']:
        assert r['inventory_t'] == pytest.approx(r['opening_inventory_t']+r['delivered_t']-r['losses_t']-r['served_t'])
        assert 0 <= r['inventory_t'] <= r['capacity_t']+1e-8
    for r in result['yearly_balance']:
        assert r['closing_inventory_t'] == pytest.approx(r['opening_inventory_t']+r['delivered_t']-r['losses_t']-r['served_t'])
        assert r['served_critical_t'] <= r['served_t']+1e-8
    for r in result['financial_breakdown']:
        assert r['total_mln'] == pytest.approx(sum(r[k] for k in ['procurement_mln','reservation_mln','holding_mln','fixed_opex_mln','capex_mln']))


def test_stress_isolation(case, base):
    plan = make_plan(case, 'lunar')
    before = copy.deepcopy((case, plan, base))
    nominal = evaluate(case, plan, base)
    stress = evaluate(case, plan, load_scenario('MANDATORY_STRESS'))
    for row in stress['source_schedule']:
        if row['source_id'] == 'D' and row['year'] in [2038,2039]:
            assert row['offered_volume_t'] == pytest.approx(row['ordered_volume_t']*({2038:.55,2039:.75}[row['year']]))
    for n,s in zip(nominal['financial_breakdown'],stress['financial_breakdown']):
        assert s['reservation_mln'] == n['reservation_mln']
        assert s['capex_mln'] == n['capex_mln']
    assert (case,plan,base) == before
    assert nominal == evaluate(case,plan,base)


def test_lead_times(case):
    assert [lead_days(r) for r in case['supply_sources']] == [365,122,730,61,42]


def test_late_order_has_no_physical_supply(case,plan,base):
    order = plan['decisions']['supply_orders'][0]
    order['order_day'] = 0
    r = evaluate(case,plan,base)
    assert any(c['rule_id']=='LEAD_TIME' for c in failures(r))
    assert r['source_schedule'][0]['delivered_volume_t'] == 0
    assert r['summary']['shortage_t'] > 0


def test_capacity_not_silently_changed(case,plan,base):
    plan['decisions']['capacity_reservations'][0]['reserved_capacity_t'] = 1000
    r = evaluate(case,plan,base)
    assert any(c['rule_id']=='CAPACITY_EXCEEDED' for c in failures(r))
    assert r['source_schedule'][0]['reserved_capacity_t'] == 1000

@pytest.mark.parametrize('value', [-1, float('nan'), float('inf'), True])
def test_invalid_numbers(case,plan,base,value):
    plan['decisions']['capacity_reservations'][0]['reserved_capacity_t'] = value
    with pytest.raises(InputError): evaluate(case,plan,base)


def test_unknown_source_and_duplicates(case,plan,base):
    plan['decisions']['supply_orders'].append(copy.deepcopy(plan['decisions']['supply_orders'][0]))
    with pytest.raises(InputError,match='DUPLICATE'): evaluate(case,plan,base)
    plan['decisions']['supply_orders'].pop()
    plan['decisions']['supply_orders'][0]['source_id']='typo'
    with pytest.raises(InputError,match='UNKNOWN_SOURCE'): evaluate(case,plan,base)


def test_organizer_invalid_scenario():
    with pytest.raises(ValidationError):
        schema_validate(load_json(REFERENCE/'examples/invalid_plan_examples/malformed_scenario.json'), 'scenario')


def test_organizer_negative_reservation(case,base):
    with pytest.raises(InputError):
        evaluate(case,load_json(REFERENCE/'examples/invalid_plan_examples/negative_reservation.json'),base)


def test_overflow_detected_intrayear(case,plan,base):
    for r in plan['decisions']['supply_orders']:
        if r['year']==2035:
            r['end_day']=1
    r=evaluate(case,plan,base)
    assert any(c['rule_id']=='STORAGE_OVERFLOW' for c in failures(r))
    assert r['yearly_balance'][0]['rejected_delivery_t'] > 0
    assert r['yearly_balance'][0]['shortage_t'] > 0


def test_early_commission_not_available(case,plan,base):
    plan['decisions']['investments'][0]['commission_day']=365
    r=evaluate(case,plan,base)
    assert any(c['rule_id']=='COMMISSIONING_INVALID' for c in failures(r))
    assert sum(x['delivered_volume_t'] for x in r['source_schedule'] if x['source_id']=='C') == 0
    json.dumps(r,allow_nan=False)


def test_zero_demand(case,plan,base):
    for r in case['demand']:
        r['base_total_t']=r['base_critical_t']=0
    r=evaluate(case,plan,base)
    assert r['summary']['min_total_service']==1


def test_critical_not_additive(case,plan,base):
    case['demand'][0]['base_critical_t']=101
    with pytest.raises(InputError,match='CRITICAL_EXCEEDS_TOTAL'): evaluate(case,plan,base)


def test_partial_contract(case,plan,base):
    res=plan['decisions']['capacity_reservations'][0]
    order=plan['decisions']['supply_orders'][0]
    res['start_day']=order['start_day']=183
    res['reserved_capacity_t']=100
    order['ordered_volume_t']=40
    r=evaluate(case,plan,base)['source_schedule'][0]
    assert r['reservation_mln']==pytest.approx(.45*100*183/365)
    assert r['payable_volume_t']==pytest.approx(max(40,.7*100*183/365))


def test_reserve_not_emergency_capacity(case,plan,base):
    plan['decisions']['inventory_policy']['opening_stock_t']=0
    r=evaluate(case,plan,base)
    assert any(c['rule_id']=='RESERVE_45D' and c['period']==2035 for c in failures(r))


def test_capex_and_opex(case,base):
    r=evaluate(case,make_plan(case,'lunar'),base)
    assert sum(x['capex_mln'] for x in r['financial_breakdown']) == 1790
    assert r['financial_breakdown'][3]['fixed_opex_mln'] == pytest.approx(82)


def test_stress_without_zbo_flags_loss(case,plan):
    plan['decisions']['investments']=[i for i in plan['decisions']['investments'] if i['investment_id']!='ZBO']
    r=evaluate(case,plan,load_scenario('MANDATORY_STRESS'))
    assert len([c for c in failures(r) if c['rule_id']=='STRESS_LOSS_LIMIT'])==3


def test_emergency_streak_is_real_check(case,plan,base):
    for y in [2035,2036,2037]:
        plan['decisions']['supply_orders'].append(dict(source_id='E',year=y,ordered_volume_t=1,start_day=1,end_day=365,order_day=(y-2035)*365-42))
        plan['decisions']['capacity_reservations'].append(dict(source_id='E',year=y,reserved_capacity_t=1,start_day=1,end_day=365))
    r=evaluate(case,plan,base)
    bad=[c for c in failures(r) if c['rule_id']=='EMERGENCY_BASE_STREAK']
    assert len(bad)==1 and bad[0]['period']==2037 and bad[0]['actual']==3


def test_lunar_late_funding_not_commissioned(case,base):
    plan=make_plan(case,'lunar')
    plan['decisions']['investments'][-1]['decision_day']=1095
    r=evaluate(case,plan,base)
    assert any(c['rule_id']=='COMMISSIONING_INVALID' for c in failures(r))
    assert sum(s['delivered_volume_t'] for s in r['source_schedule'] if s['source_id']=='D')==0


def test_annual_top_not_daily(case,plan,base):
    plan['decisions']['supply_orders'][0]['ordered_volume_t']=0
    plan['decisions']['capacity_reservations'][0]['reserved_capacity_t']=100
    r=evaluate(case,plan,base)
    assert r['source_schedule'][0]['procurement_mln']==pytest.approx(.7*100*6.2)


def test_case_prices_used_without_hardcoded_multiplier(case,plan,base):
    before=evaluate(case,plan,base)
    case['supply_sources'][0]['variable_cost_mln_per_t']*=2
    after=evaluate(case,plan,base)
    expected=sum(r['procurement_mln'] for r in before['source_schedule'] if r['source_id']=='A')+before['pre_horizon']['procurement_mln']
    assert after['summary']['total_cost_mln']-before['summary']['total_cost_mln']==pytest.approx(expected)


def test_loss_switch_at_day_of_commission(case,plan,base):
    plan['decisions']['investments'][1]['decision_day']=500
    plan['decisions']['investments'][1]['commission_day']=500
    result=evaluate(case,plan,base)
    for i in [499,500]:
        d=result['inventory_trace'][i]
        assert d['losses_t']/d['delivered_t']==pytest.approx(.045 if i==499 else .012)
