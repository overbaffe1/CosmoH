import copy
import pytest
from fuel.io import load_case,digest
from fuel.planning import make_plan
from fuel.recourse import emergency_response
from fuel.study import response_grid


def test_grid_keeps_inputs_and_matches_direct_response():
    c=load_case();p=make_plan(c,'lunar');before=copy.deepcopy((c,p))
    g=response_grid(c,p,shares=(0,.5,1),delays=(0,330))
    assert (c,p)==before and len(g['rows'])==6
    assert g==response_grid(c,p,shares=(0,.5,1),delays=(0,330))
    for row in g['rows']:
        r=emergency_response(c,p,delivery_share=row['delivery_share'],observed_after_days=row['observed_after_days'])
        assert row['response_sha256']==digest(r)
        assert row['after']==r['after']['summary']
        assert row['prefix_unchanged'] and row['commitments_unchanged']
    immediate=next(r for r in g['rows'] if r['delivery_share']==.5 and r['observed_after_days']==0)
    assert immediate['after']['violations']==0
    assert immediate['added_order_t']==60
    assert all(r['added_order_t']==0 for r in g['rows'] if r['delivery_share']==1)


@pytest.mark.parametrize('shares,delays',[((),(0,)),((0,),()),((0,0),(0,)),((0,),(0,0))])
def test_grid_rejects_ambiguous_axes(shares,delays):
    c=load_case()
    with pytest.raises(ValueError,match='STUDY_GRID'):response_grid(c,make_plan(c,'lunar'),shares,delays)


def test_heatmap_contains_all_sampled_values():
    from tools.evidence import heatmap
    c=load_case();g=response_grid(c,make_plan(c,'lunar'),shares=(0,.5,1),delays=(0,330))
    svg=heatmap(g)
    assert svg.count('<title>')==6 and 'без сбоя' in svg
    assert 'наруш.' in svg and '0,00 т' in svg


def test_published_grid_is_reproducible_not_hand_entered():
    from fuel.io import ROOT,load_json
    c=load_case();actual=response_grid(c,make_plan(c,'lunar'))
    published=load_json(ROOT/'docs/evidence/response-grid.json')
    published.pop('summary_sha256')
    assert actual==published


def test_measurement_statistics_and_freshness():
    import math
    from fuel.io import ROOT,load_json
    from tools.evidence_publish import read_evidence
    s=load_json(ROOT/'docs/numbers.json');_,m=read_evidence(s)
    for t in m['timings'].values():
        raw=sorted(t['samples_ms']);assert len(raw)==15
        assert all(math.isfinite(x) and x>=0 for x in raw)
        assert t['median_ms']==raw[math.ceil(.5*len(raw))-1]
        assert t['p95_ms']==raw[math.ceil(.95*len(raw))-1]
    bad=copy.deepcopy(s);bad['status']='changed'
    with pytest.raises(ValueError,match='STALE_GRID'):read_evidence(bad)


def test_evidence_route_and_enriched_slides():
    from fastapi.testclient import TestClient
    from fuel.api import app
    from fuel.io import ROOT,load_json
    from tools.defense import slides_for
    from tools.evidence_publish import enrich_slides
    s=load_json(ROOT/'docs/numbers.json');slides=enrich_slides(slides_for(s),s)
    assert len(slides)==12 and len(slides[8]['visual']['study']['rows'])==35
    assert slides[10]['visual']['type']=='demo_proof'
    r=TestClient(app).get('/evidence')
    assert r.status_code==200 and 'Это сохранённый протокол' in r.text
    assert '15 последовательных повторов' in r.text
