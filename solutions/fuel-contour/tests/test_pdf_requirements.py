"""Regression tests tied to the newly available case PDF, pages 7–13."""
import copy
import csv
import json
import zipfile
import io
import pytest
from fastapi.testclient import TestClient
from fuel.api import app
from fuel.io import load_scenario, export_result
from fuel.engine import evaluate, lead_days
from fuel.planning import make_plan
from fuel.analysis import (compare_decisions, parameter_sensitivity, stress_attribution,
                           price_crossover, monte_carlo, risk_analysis)
from fuel.datasets import research_copy
from fuel.validation import InputError


def test_preparation_cost_recognized_in_first_year_only(case, plan, base):
    r=evaluate(case,plan,base)
    first=r['financial_breakdown'][0]
    initial=r['pre_horizon']
    procurement=sum(s['procurement_mln'] for s in r['source_schedule'] if s['year']==2035)
    assert first['procurement_mln']==pytest.approx(procurement+initial['procurement_mln'])
    assert first['preparation_included_mln']==initial['total_mln']
    assert all(f['preparation_included_mln']==0 for f in r['financial_breakdown'][1:])
    assert sum(f['total_mln'] for f in r['financial_breakdown'])==pytest.approx(r['summary']['total_cost_mln'])
    assert initial['cashflow_recognition_year']==2035
    assert initial['included_in_financial_breakdown'] is True
    # Prior total retained, only year attribution corrected.
    assert r['summary']['total_cost_mln']==pytest.approx(11071.926209100871)


@pytest.mark.parametrize('field,value,rule', [
    ('opening_order_day',-10,'PREPARATION_LEAD_TIME'),
    ('opening_delivery_day',0,'PREPARATION_DELIVERY_BEFORE_HORIZON')])
def test_invalid_preparation_never_creates_free_stock(case,plan,base,field,value,rule):
    plan['decisions']['inventory_policy'][field]=value
    r=evaluate(case,plan,base)
    assert any(c['rule_id']==rule and not c['passed'] for c in r['constraint_checks'])
    assert r['yearly_balance'][0]['opening_inventory_t']==0
    assert r['pre_horizon']['delivered_gross_t']==0
    assert r['pre_horizon']['procurement_mln']>0  # committed payment not forgiven


def test_historical_channel_availability_is_checked(case,plan,base):
    plan['assumptions']['preparation_availability']['A']=-100
    r=evaluate(case,plan,base)
    assert any(c['rule_id']=='PREPARATION_AVAILABILITY' and not c['passed'] for c in r['constraint_checks'])
    assert r['yearly_balance'][0]['opening_inventory_t']==0


@pytest.mark.parametrize('rate', [.0,.05,.10])
def test_real_discount_rate_applied_with_declared_end_year_convention(case,plan,base,rate):
    plan['assumptions']['discount_rate']['value']=rate
    r=evaluate(case,plan,base)
    expected=sum(f['total_mln']/(1+rate)**(i+1) for i,f in enumerate(r['financial_breakdown']))
    assert r['summary']['discounted_cost_mln']==pytest.approx(expected)
    assert r['summary']['cost_per_served_t_mln']==pytest.approx(r['summary']['total_cost_mln']/1390)


@pytest.mark.parametrize('rate', [-.1, float('nan'), 1.01, True])
def test_invalid_discount_rates_rejected(case,plan,base,rate):
    plan['assumptions']['discount_rate']['value']=rate
    with pytest.raises(InputError):evaluate(case,plan,base)


@pytest.mark.parametrize('strategy', ['earth','lunar'])
def test_ex_ante_stress_design_obeys_capacity_dates_and_reserve(case,strategy):
    stress=load_scenario('MANDATORY_STRESS')
    plan=make_plan(case,strategy,stress)
    r=evaluate(case,plan,stress)
    assert r['summary']['violations']==0
    assert r['summary']['shortage_t']==0
    assert r['summary']['min_total_service']==pytest.approx(1)
    assert r['summary']['min_commercial_service']==pytest.approx(1)
    assert plan['scenario_id']=='MANDATORY_STRESS'
    sources={s['source_id']:s for s in case['supply_sources']}
    for o in plan['decisions']['supply_orders']:
        assert (o['year']-2035)*365+o['start_day']-1-o['order_day']>=lead_days(sources[o['source_id']])
    assert max(y['max_inventory_t'] for y in r['yearly_balance'])<=120


def test_redesign_comparison_is_two_by_two_and_keeps_old_stress(case,plan,base):
    original=copy.deepcopy(plan)
    stress=load_scenario('MANDATORY_STRESS')
    alternative=make_plan(case,'earth',stress)
    comparison=compare_decisions(case,plan,alternative,base,stress)
    assert len(comparison['matrix'])==4
    assert comparison['avoided_stress_shortage_t']==pytest.approx(80.7054794520558)
    assert comparison['incremental_stress_cost_mln']>0
    assert comparison['earliest_changed_order_day']<1095  # decisions precede 2038 event
    assert len(comparison['stakeholders'])==5
    assert plan==original


def test_stress_attribution_telescopes_to_joint_stress(case,plan,base):
    stress=load_scenario('MANDATORY_STRESS')
    rows=stress_attribution(case,plan,stress)['steps']
    r=evaluate(case,plan,stress)
    b=evaluate(case,plan,base)
    assert rows[-1]['total_cost_mln']==r['summary']['total_cost_mln']
    assert sum(x['delta_cost_mln'] for x in rows)==pytest.approx(r['summary']['total_cost_mln']-b['summary']['total_cost_mln'])
    assert sum(x['delta_shortage_t'] for x in rows)==pytest.approx(r['summary']['shortage_t']-b['summary']['shortage_t'])


def test_parameter_sweep_includes_implementation_uncertainty_without_mutation(case,plan):
    before=copy.deepcopy((case,plan))
    s=parameter_sensitivity(case,plan)
    params={x['parameter'] for x in s['points']}
    assert {'lead_time_policy','zbo_delay_days','emergency_base_definition','real_discount_rate','Earth-Core price'}<=params
    assert all('min_inventory_t' in row and 'shortage_t' in row for row in s['points'])
    assert (case,plan)==before


def test_lower_lead_bound_can_change_late_order_outcome(case,plan):
    # Same commission, same plan; one order prepared 18 months, not 24, in advance.
    order=next(o for o in plan['decisions']['supply_orders'] if o['source_id']=='C' and o['year']==2037)
    order['order_day']=730-548
    upper=evaluate(case,plan,{'scenario_id':'TEAM_UPPER','status':'TEAM_ASSUMPTION'})
    lower=evaluate(case,plan,{'scenario_id':'TEAM_LOWER','status':'TEAM_ASSUMPTION','implementation_assumptions':{'lead_time_policy':'lower'}})
    assert any(c['rule_id']=='LEAD_TIME' and not c['passed'] for c in upper['constraint_checks'])
    assert not any(c['rule_id']=='LEAD_TIME' and not c['passed'] for c in lower['constraint_checks'])


def test_zbo_delay_changes_real_storage_mode(case,plan):
    s={'scenario_id':'TEAM_DELAY','status':'TEAM_ASSUMPTION','implementation_assumptions':{'zbo_delay_days':90}}
    r=evaluate(case,plan,s)
    for t,rate in [(365,.045),(454,.045),(455,.012)]:
        row=r['inventory_trace'][t]
        assert row['losses_t']/row['delivered_t']==pytest.approx(rate)


def test_emergency_definition_research_changes_check_not_supply(case,plan):
    for year in [2035,2036,2037]:
        plan['decisions']['supply_orders'].append(dict(source_id='E',year=year,ordered_volume_t=1,start_day=1,end_day=365,order_day=(year-2035)*365-42))
        plan['decisions']['capacity_reservations'].append(dict(source_id='E',year=year,reserved_capacity_t=1,start_day=1,end_day=365))
    s={'scenario_id':'TEAM_E','status':'TEAM_ASSUMPTION'}
    a=evaluate(case,plan,s)
    s['implementation_assumptions']={'emergency_base_definition':'majority'}
    b=evaluate(case,plan,s)
    assert a['yearly_balance']==b['yearly_balance']
    assert any(c['rule_id']=='EMERGENCY_BASE_STREAK' and not c['passed'] for c in a['constraint_checks'])
    assert not any(c['rule_id']=='EMERGENCY_BASE_STREAK' and not c['passed'] for c in b['constraint_checks'])


def test_implementation_changes_cannot_be_disguised_as_base(case,plan,base):
    base['implementation_assumptions']={'lead_time_policy':'lower'}
    with pytest.raises(InputError,match='REQUIRE_TEAM'):evaluate(case,plan,base)


@pytest.mark.parametrize('entry', [
    {'variable_price_multiplier':{'2039':1.5}},
    {'demand_multiplier':{'Earth-Core':{'2039':1.5}}},
    {'unused_magic_multiplier':5},
    {'loss_ceiling':{'enabled':True,'from_year':2038,'max_losses_divided_by_throughput':2}}])
def test_malformed_scenario_not_silently_ignored(case,plan,entry):
    with pytest.raises(InputError):evaluate(case,plan,{'scenario_id':'TEAM_BAD','status':'TEAM_ASSUMPTION',**entry})


def test_common_year_monte_carlo_is_seeded_and_marked(case,plan):
    a=monte_carlo(case,plan,20,2035,'common_year')
    assert a==monte_carlo(case,plan,20,2035,'common_year')
    assert a['dependence']=='common_year'
    assert a['runs']!=monte_carlo(case,plan,20,2035,'independent')['runs']


def test_price_crossover_has_reproducible_bracket(case):
    r=price_crossover(case,make_plan(case,'lunar'),make_plan(case,'earth'))
    lo,hi=r['bracket']
    assert 1 < lo < hi < 3 and hi-lo<1e-6


def test_geopolitical_measure_addresses_price_exposure(case,plan,base):
    r=next(r for r in risk_analysis(case,plan,evaluate(case,plan,base)) if r['risk_id']=='GEO')
    assert r['residual_consequence']['total_cost_mln'] < r['result_summary']['total_cost_mln']
    assert len(r['stakeholder_effects'])==5
    assert r['mitigation_baseline_cost_mln']>0
    assert r['mitigation_nominal_summary']['violations']==0
    assert r['residual_consequence']['violations']==0
    assert 'Ex-ante' in r['tested_mitigation']


def test_input_copy_provenance_and_restoration(case,plan,base):
    rows=copy.deepcopy(case['demand']);rows[0]['base_total_t']=105
    changed=research_copy(case,{'demand':rows,'basis':'TEAM research +5 tonnes'})
    assert changed['demand'][0]['status']=='TEAM_ASSUMPTION'
    assert changed['constraints']==case['constraints']
    assert case['demand'][0]['base_total_t']==100
    assert changed['research_provenance']['changes'][0]['before']['base_total_t']==100
    r=evaluate(changed,plan,{'scenario_id':'TEAM_COPY','status':'TEAM_ASSUMPTION'})
    assert r['yearly_balance'][0]['demand_t']==105


@pytest.mark.parametrize('patch', [{'constraints':[],'basis':'not allowed'},{'demand':[],'basis':'empty'},{'basis':''}])
def test_research_copy_cannot_remove_control_limits(case,patch):
    with pytest.raises(InputError):research_copy(case,patch)


def test_api_research_copy_and_full_export(plan,case):
    client=TestClient(app)
    rows=copy.deepcopy(case['demand']);rows[0]['base_total_t']=105
    request={'plan':plan,'research_case_patch':{'demand':rows,'basis':'illustrative change'}}
    assert client.post('/api/run',json=request).status_code==422
    request['research_scenario']={'scenario_id':'TEAM_COPY','status':'TEAM_ASSUMPTION'}
    run=client.post('/api/run',json=request)
    assert run.status_code==200
    exported=client.post('/api/export',json=request)
    assert exported.status_code==200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
        assert {'case_demand.csv','case_supply_sources.csv','plan.json','case.json','scenario.json','roadmap.csv','scenario_comparison.csv'}<=set(z.namelist())
        result=json.loads(z.read('result.json'))
        assert result['summary']==run.json()['summary']
        comparisons=list(csv.DictReader(io.StringIO(z.read('scenario_comparison.csv').decode())))
        assert all(row['scenario_id'].startswith('TEAM_COPY_') for row in comparisons)


def test_stress_preset_api_and_explicit_decision_comparison(plan):
    client=TestClient(app)
    alternative=client.get('/api/plans/earth-stress').json()
    request={'plan':plan,'alternative_plan':alternative}
    r=client.post('/api/analysis/adaptation',json=request)
    assert r.status_code==200
    assert r.json()['avoided_stress_shortage_t']>0
    exported=client.post('/api/export',json=request)
    with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
        assert 'decision_comparison.csv' in z.namelist()
        assert 'decision_changes.csv' in z.namelist()


def test_comparing_alternatives_with_different_rates_is_rejected(case,plan,base):
    alternative=make_plan(case,'earth',load_scenario('MANDATORY_STRESS'))
    alternative['assumptions']['discount_rate']['value']=.05
    with pytest.raises(InputError,match='DISCOUNT_BASIS_MISMATCH'):
        compare_decisions(case,plan,alternative,base,load_scenario('MANDATORY_STRESS'))


def test_post_commission_partial_period_drives_top_and_reservation(case,plan,base):
    # C commissioned at day 900 in 2037; no TOP on unavailable 170 days.
    plan['decisions']['investments'][0]['commission_day']=900
    order=next(o for o in plan['decisions']['supply_orders'] if o['source_id']=='C' and o['year']==2037)
    order.update(ordered_volume_t=10,start_day=171,end_day=365,order_day=0)
    reservation=next(r for r in plan['decisions']['capacity_reservations'] if r['source_id']=='C' and r['year']==2037)
    reservation.update(reserved_capacity_t=100,start_day=171,end_day=365)
    r=evaluate(case,plan,base)
    contract=next(s for s in r['source_schedule'] if s['source_id']=='C' and s['year']==2037)
    assert contract['contract_period_fraction']==pytest.approx(195/365)
    assert contract['procurement_mln']==pytest.approx(max(10,.5*100*195/365)*7.1)
    assert contract['reservation_mln']==pytest.approx(.3*100*195/365)
    reservation['start_day']=1
    invalid=evaluate(case,plan,base)
    assert any(c['rule_id']=='RESERVATION_BEFORE_COMMISSIONING' and not c['passed'] for c in invalid['constraint_checks'])


def test_independent_one_year_closed_form_cost_and_balance(case,plan,base):
    # Synthetic V11: flat 100 t gross inflow, 100 t demand, 20 t opening, BASE storage.
    case['demand']=case['demand'][:1]
    plan['decisions']['investments']=[]
    plan['decisions']['supply_orders']=[dict(source_id='A',year=2035,ordered_volume_t=100,start_day=1,end_day=365,order_day=-365)]
    plan['decisions']['capacity_reservations']=[dict(source_id='A',year=2035,reserved_capacity_t=100,start_day=1,end_day=365)]
    result=evaluate(case,plan,base)
    net=100*(1-.045)
    # Closed form for daily arrival at start, uniform withdrawal; derived independently of loop.
    average_inventory=20+(net-100)/2+net/(2*365)
    initial_cost=(20/(1-.045))*(6.2+.45)+20*.72/365
    expected=100*6.2+100*.45+average_inventory*.72+initial_cost
    assert result['summary']['total_cost_mln']==pytest.approx(expected)
    assert result['yearly_balance'][0]['closing_inventory_t']==pytest.approx(15.5)
    assert result['yearly_balance'][0]['losses_t']==pytest.approx(4.5)
    assert result['summary']['violations']==0


@pytest.mark.parametrize('field,value', [('assumptions',None),('discount_rate','5%'),('preparation_availability',[])] )
def test_malformed_assumptions_give_actionable_422(plan,field,value):
    if field=='assumptions':plan[field]=value
    else:plan['assumptions'][field]=value
    response=TestClient(app).post('/api/run',json={'plan':plan})
    assert response.status_code==422
    assert 'MUST_BE_OBJECT' in response.json()['detail']


def test_unexposed_lunar_risk_does_not_charge_earth_plan_for_useless_measure(case,plan,base):
    row=next(r for r in risk_analysis(case,plan,evaluate(case,plan,base)) if r['risk_id']=='LUNAR_OUTAGE')
    assert row['material_exposure'] is False
    assert row['exposure_t']==0
    assert row['mitigation_baseline_cost_mln']==0
    assert row['mitigation_incremental_cost_mln']==0


def test_late_lunar_commission_does_not_raise_first_year_reliability(case):
    from fuel.analysis import reliability
    source=next(s for s in case['supply_sources'] if s['source_id']=='D')
    assert reliability(source,2039,2039)==pytest.approx(.78)
    assert reliability(source,2039,2038)==pytest.approx(.90)


@pytest.mark.parametrize('profile',['constant:1.1','constant:nan','constant:-0.1'])
def test_invalid_reliability_metadata_is_not_used_as_probability(case,plan,profile):
    case['supply_sources'][0]['reliability_profile']=profile
    with pytest.raises(InputError,match='RELIABILITY_OUT_OF_RANGE'):monte_carlo(case,plan,1)
