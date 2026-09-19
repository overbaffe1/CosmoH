from fastapi.testclient import TestClient
from fuel.api import app
from fuel.engine import evaluate
from fuel.io import load_case,load_scenario


def test_showcase_is_real_core_output_and_exposes_bad_combinations():
    c=TestClient(app);r=c.get('/api/showcase');assert r.status_code==200
    data=r.json()
    assert len(data['architectures'])==2
    for architecture in data['architectures'].values():
        runs=architecture['runs']
        assert runs['base']['summary']['violations']==0
        assert runs['stress']['summary']['shortage_t']>0
        assert runs['prepared']['summary']['violations']==0
        assert runs['prepared_base']['summary']['violations']>0
        assert runs['base']['summary']==evaluate(load_case(),architecture['plan'],load_scenario('BASE'))['summary']
    assert c.get('/api/showcase').json()==data


def test_showcase_planner_and_material_routes_are_separate_and_whitelisted():
    c=TestClient(app)
    assert 'calculator.js' in c.get('/').text
    assert 'showcase.js' in c.get('/demo').text
    assert 'app.js' in c.get('/planner').text
    assert c.get('/presentation').status_code==200
    assert c.get('/materials/PRESENTATION.pdf').headers['content-type']=='application/pdf'
    for filename in ['numbers.json','../fuel/api.py','unknown.txt']:
        assert c.get('/materials/'+filename).status_code==404


def test_theme_and_plain_language_help_are_available_offline():
    c=TestClient(app)
    for route in ['/', '/planner']:
        page=c.get(route).text
        assert '/assets/theme.js' in page and 'id="themeToggle"' in page
    home=c.get('/demo').text
    for component in ['plainGuide','decisionMeaning','chartData','resetView']:
        assert f'id="{component}"' in home
    assert 'data-mode="prepared_base"' in home
    theme=c.get('/assets/theme.js')
    assert theme.status_code==200 and 'localStorage' in theme.text and 'catch' in theme.text


def test_calculator_routes_and_user_parameters():
    from fuel.planning import make_plan
    c=TestClient(app);case=load_case();p=make_plan(case,'lunar')
    home=c.get('/').text
    for ident in ['calculator','environment','orderInputs','investmentInputs','calculate','projectFile']:
        assert f'id="{ident}"' in home
    assert 'target="_blank"' not in home
    assert c.get('/evidence/').status_code==200
    assert c.get('/materials/TALK_4_MIN.txt').status_code==200
    original=evaluate(case,p,load_scenario('BASE'))['summary']
    p['decisions']['inventory_policy']['opening_stock_t']=30
    result=c.post('/api/run',json={'plan':p,'scenario_id':'BASE'})
    assert result.status_code==200
    assert result.json()['summary']['total_cost_mln']!=original['total_cost_mln']
    assert load_case()==case
