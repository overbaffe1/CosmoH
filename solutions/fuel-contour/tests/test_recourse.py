import copy
import pytest
from fastapi.testclient import TestClient
from fuel.api import app
from fuel.io import load_case
from fuel.planning import make_plan
from fuel.recourse import emergency_response
from fuel.validation import InputError


def test_new_emergency_contract_does_not_cancel_or_rewrite_commitments():
    c=load_case();p=make_plan(c,'lunar');old=copy.deepcopy(p)
    r=emergency_response(c,p)
    assert p==old and r['original_commitments_unchanged']
    assert r['prefix_unchanged_until_arrival']
    new=r['response_plan']['decisions']
    for name in ('supply_orders','capacity_reservations'):
        assert new[name][:-1]==p['decisions'][name]
    assert new['investments']==p['decisions']['investments']
    assert new['inventory_policy']==p['decisions']['inventory_policy']
    order=new['supply_orders'][-1]
    assert order['order_day']==r['observed_day']
    assert order['start_day']==43 and r['lead_time_days']==42
    assert r['added_order_t']==pytest.approx(80*323/365)
    assert r['after']['summary']['shortage_t']==0
    assert r['after']['summary']['violations']>0  # Do not falsely claim universal recovery.
    assert r['incremental_cost_mln']>0
    original_rows=[x for x in r['before']['source_schedule'] if x['source_id']!='E']
    after_rows=[x for x in r['after']['source_schedule'] if x['source_id']!='E']
    assert original_rows==after_rows  # Same paid volumes including the failed Lunar order.
    for a,b in zip(r['before']['inventory_trace'],r['after']['inventory_trace']):
        if (a['year']-2035)*365+a['day']-1 < r['first_possible_arrival_day']:assert a==b


@pytest.mark.parametrize('delay',[0,90,180,330])
def test_response_is_deterministic_and_no_past_service_is_repaired(delay):
    c=load_case();p=make_plan(c,'lunar')
    r=emergency_response(c,p,observed_after_days=delay)
    assert r==emergency_response(c,p,observed_after_days=delay)
    assert r['prefix_unchanged_until_arrival']
    if delay==330:
        assert r['action']=='too_late_this_year'
        assert r['response_plan']==p
        assert r['incremental_cost_mln']==0
    else:
        assert r['response_plan']['decisions']['supply_orders'][-1]['order_day']==1095+delay


def test_no_exposure_and_existing_contract_are_not_silently_modified():
    c=load_case();p=make_plan(c,'earth')
    assert emergency_response(c,p)['action']=='no_remaining_exposure'
    p=make_plan(c,'lunar');r=emergency_response(c,p)
    locked=r['response_plan']
    result=emergency_response(c,locked)
    assert result['action']=='blocked_existing_emergency_contract'
    assert result['response_plan']==locked
    assert emergency_response(c,p,delivery_share=1)['action']=='no_remaining_exposure'
    assert emergency_response(c,p,max_emergency_t=0)['action']=='zero_purchase_limit'


@pytest.mark.parametrize('kwargs',[{'delivery_share':float('nan')},{'observed_after_days':-1},{'observed_after_days':365},{'event_year':2037},{'max_emergency_t':-1}])
def test_recourse_rejects_invalid_inputs(kwargs):
    c=load_case()
    with pytest.raises(InputError):emergency_response(c,make_plan(c,'lunar'),**kwargs)


def test_api_response_contains_full_inputs_and_honest_residual():
    c=load_case();client=TestClient(app)
    response=client.post('/api/recourse',json={'plan':make_plan(c,'lunar'),'observed_after_days':90})
    assert response.status_code==200
    r=response.json()
    assert r['after']['summary']['shortage_t']>0
    assert r['residual_failed_rules']
    assert client.post('/api/recourse',json={'plan':make_plan(c,'lunar'),'observed_after_days':400}).status_code==422


def test_partial_disruption_can_be_feasible_without_changing_old_orders():
    c=load_case();p=make_plan(c,'lunar');before=copy.deepcopy(c)
    r=emergency_response(c,p,delivery_share=.5)
    assert r['added_order_t']==pytest.approx(60)
    assert r['after']['summary']['shortage_t']==0
    assert r['after']['summary']['violations']==0
    assert r['original_commitments_unchanged'] and c==before
    assert len(r['stakeholders'])==5


def test_operator_purchase_limit_is_a_real_limit_not_a_budget_override():
    c=load_case();p=make_plan(c,'lunar')
    r=emergency_response(c,p,max_emergency_t=20)
    assert r['added_order_t']==20
    assert r['after']['summary']['shortage_t']>0
    assert r['incremental_cost_mln']>0


def test_integral_float_calendar_arguments_are_canonicalized():
    c=load_case();p=make_plan(c,'lunar')
    assert emergency_response(c,p,event_year=2038.0,observed_after_days=90.0)==emergency_response(c,p,event_year=2038,observed_after_days=90)
