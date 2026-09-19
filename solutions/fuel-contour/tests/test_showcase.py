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
    assert 'showcase.js' in c.get('/').text
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
    home=c.get('/').text
    for component in ['plainGuide','decisionMeaning','chartData','resetView']:
        assert f'id="{component}"' in home
    assert 'data-mode="prepared_base"' in home
    theme=c.get('/assets/theme.js')
    assert theme.status_code==200 and 'localStorage' in theme.text and 'catch' in theme.text
