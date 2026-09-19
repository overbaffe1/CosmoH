import copy
import csv
import io
import zipfile
import pytest
from fastapi.testclient import TestClient
from fuel.api import app
from fuel.io import export_result, load_json, save_json, load_scenario, schema_validate
from fuel.engine import evaluate
from fuel.analysis import sensitivity, monte_carlo, risk_analysis, extension_demo, mcda, demand_scenario


def test_roundtrip_export(case,plan,base,tmp_path):
    save_json(tmp_path/'plan.json',plan)
    reopened=load_json(tmp_path/'plan.json')
    assert reopened==plan
    result=evaluate(case,plan,base)
    assert result==evaluate(case,reopened,base)
    export_result(result,tmp_path/'export')
    assert load_json(tmp_path/'export/result.json')==result
    with (tmp_path/'export/yearly_balance.csv').open() as f:
        rows=list(csv.DictReader(f))
    assert float(rows[0]['delivered_t'])==result['yearly_balance'][0]['delivered_t']
    assert rows[0]['scenario_id']=='BASE'


def test_research_immutable_and_seeded(case,plan,base):
    before=copy.deepcopy((case,plan))
    assert monte_carlo(case,plan,8,42)==monte_carlo(case,plan,8,42)
    assert monte_carlo(case,plan,8,42)!=monte_carlo(case,plan,8,43)
    nominal=evaluate(case,plan,base)
    risks=risk_analysis(case,plan,nominal)
    assert risks[1]['risk_id']=='GEO'
    assert risks[1]['financial_consequence_mln'] > 0
    assert risks[1]['physical_consequence_t']==pytest.approx(0)
    assert (case,plan)==before
    assert evaluate(case,plan,base)==nominal


def test_low_high_preserves_critical_share(case,plan):
    for k in ['low','high']:
        r=evaluate(case,plan,demand_scenario(case,k))
        for original,new in zip(case['demand'],r['yearly_balance']):
            assert new['demand_t']==pytest.approx(original[k+'_total_t'])
            assert new['critical_demand_t']/new['demand_t']==pytest.approx(original['base_critical_t']/original['base_total_t'])


def test_extensions(case,plan):
    r=extension_demo(case,plan)
    assert r['yearly_balance'][-1]['year']==2041
    assert any(x['source_id']=='Source-X' for x in r['source_schedule'])
    assert 'extension' in r['assumptions_reference']


def test_source_x_exact_equivalence(case,plan,base):
    before=evaluate(case,plan,base)['summary']
    x=copy.deepcopy(case['supply_sources'][1]);x.update(source_id='X',name='X')
    case['supply_sources'].append(x)
    for section in ['supply_orders','capacity_reservations']:
        for r in plan['decisions'][section]:
            if r['source_id']=='B':r['source_id']='X'
    after=evaluate(case,plan,base)['summary']
    assert after==pytest.approx(before)


def test_sensitivity(case,plan):
    s=sensitivity(case,plan)
    assert len(s['points'])==8
    lo,hi=s['service_failure_bracket']
    assert lo < hi and hi-lo < 1e-6
    assert s['points'][-1]['shortage_t'] > s['points'][0]['shortage_t']


def test_api_ui_and_export(plan):
    client=TestClient(app)
    assert client.get('/').status_code==200
    assert client.get('/api/case').json()['case']['version']
    request={'plan':plan,'scenario_id':'BASE'}
    response=client.post('/api/run',json=request)
    assert response.status_code==200
    schema_validate(response.json(),'export')
    assert client.post('/api/run',json={'plan':{}}).status_code==422
    assert client.post('/api/run',json={**request,'scenario_id':'BOGUS'}).status_code==422
    assert client.post('/api/run',json={**request,'research_scenario':{'scenario_id':'BASE','status':'CASE_INPUT'}}).status_code==422
    result=client.post('/api/export',json=request)
    assert result.status_code==200
    with zipfile.ZipFile(io.BytesIO(result.content)) as z:
        assert 'result.json' in z.namelist()
        assert 'inventory_trace.csv' in z.namelist()


def test_sensitivity_does_not_invent_bracket(case,plan):
    plan['decisions']['supply_orders']=[]
    assert sensitivity(case,plan)['threshold_status']=='already_fails_at_one'
    assert sensitivity(case,plan)['service_failure_bracket'] is None


def test_research_api_restore(plan):
    client=TestClient(app)
    before=client.post('/api/run',json={'plan':plan}).json()
    scenario={'scenario_id':'TEAM_GEO','status':'TEAM_ASSUMPTION','variable_price_multiplier':{'Earth-Core':{'2039':1.5}}}
    changed=client.post('/api/run',json={'plan':plan,'research_scenario':scenario}).json()
    assert changed['summary']['total_cost_mln'] > before['summary']['total_cost_mln']
    assert client.post('/api/run',json={'plan':plan}).json()==before


def test_risk_mitigation_is_recalculated(case,plan,base):
    result=evaluate(case,plan,base)
    risks=risk_analysis(case,plan,result)
    for r in risks:
        if r['risk_id']=='EARTH_DISRUPTION':
            assert r['residual_consequence']['shortage_t'] < r['result_summary']['shortage_t']
            assert r['mitigation_incremental_cost_mln'] > 0


def test_csv_financial_total_includes_pre_horizon(case,plan,base,tmp_path):
    result=evaluate(case,plan,base)
    export_result(result,tmp_path)
    with (tmp_path/'financial_breakdown.csv').open() as f:
        annual=sum(float(r['total_mln']) for r in csv.DictReader(f))
    with (tmp_path/'pre_horizon.csv').open() as f:
        initial=float(next(csv.DictReader(f))['total_mln'])
    with (tmp_path/'summary.csv').open() as f:
        total=float(next(csv.DictReader(f))['total_cost_mln'])
    assert annual==pytest.approx(total)
    assert initial==pytest.approx(result['financial_breakdown'][0]['preparation_included_mln'])
    assert total==result['summary']['total_cost_mln']
