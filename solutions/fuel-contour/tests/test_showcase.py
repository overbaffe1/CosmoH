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
