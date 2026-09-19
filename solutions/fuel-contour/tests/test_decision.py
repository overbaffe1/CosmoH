import copy
import json
from pathlib import Path
import pytest
from fuel.decision import discount_rate_crossover, decision_brief
from fuel.engine import evaluate
from fuel.planning import make_plan
from fuel.validation import InputError


def test_rate_crossover_independent_closed_form():
    # PV Earth=110/(1+r)^2; PV Lunar=100/(1+r). Equality at r=10%.
    e=[{'year':2035,'total_mln':0}, {'year':2036,'total_mln':110}]
    l=[{'year':2035,'total_mln':100}, {'year':2036,'total_mln':0}]
    r=discount_rate_crossover(e,l,high=.2)
    assert r['bracket'][0] <= .1 <= r['bracket'][1]
    assert r['samples'][0]['lunar_minus_earth_mln'] == -10
    assert r['samples'][-1]['lunar_minus_earth_mln'] > 0


def test_case_rate_crossover_agrees_with_core(case,base):
    plans=[make_plan(case,k) for k in ('earth','lunar')]
    flows=[evaluate(case,p,base)['financial_breakdown'] for p in plans]
    before=copy.deepcopy(flows)
    r=discount_rate_crossover(*flows)
    assert .05 < r['bracket'][0] < r['bracket'][1] < .1
    for sample in r['samples']:
        for k,p in zip(('earth','lunar'),plans):
            p['assumptions']['discount_rate']['value']=sample['rate']
            assert sample[k+'_pv_mln']==pytest.approx(evaluate(case,p,base)['summary']['discounted_cost_mln'])
    assert flows == before


@pytest.mark.parametrize('low,high',[(-.1,.1),(.2,.1),(0,float('nan')),(0,True)])
def test_bad_rate_intervals(low,high):
    with pytest.raises(InputError):discount_rate_crossover([],[],low,high)


def test_no_bracket_is_not_manufactured():
    a=[{'year':2035,'total_mln':10}]; b=[{'year':2035,'total_mln':20}]
    assert discount_rate_crossover(a,b)['status_detail']=='not_bracketed'
    assert discount_rate_crossover(a,a)['status_detail']=='identical_cashflows'
    with pytest.raises(InputError,match='YEARS'):discount_rate_crossover(a,[{'year':2036,'total_mln':10}])


def summary_fixture():
    # Published suite snapshot: prevents reading an optional ignored results directory.
    s=json.loads((Path(__file__).resolve().parents[1]/'docs/numbers.json').read_text())
    s['discount_rate_crossover']=discount_rate_crossover(s['strategies']['earth']['costs_base'],s['strategies']['lunar']['costs_base'])
    return s


def test_brief_never_recommends_infeasible_cheapest_plan():
    s=summary_fixture(); before=copy.deepcopy(s)
    r=decision_brief(s)
    assert r['fixed_plans_feasible_in_both']==[]
    for environment in ('BASE','MANDATORY_STRESS'):
        assert r['choices'][environment]['economic_candidate']['violations']==0
        assert r['choices'][environment]['economic_candidate']['architecture']=='lunar'
    assert s==before
    # Even an artificially cheap infeasible result cannot win the filter.
    for v in s['strategies'].values():
        for row in v['decision_comparison']['matrix']:
            row['violations']=1;row['discounted_cost_mln']=0
    assert decision_brief(s)['choices']['BASE']['economic_candidate'] is None


def test_brief_rejects_mixed_rates():
    s=summary_fixture();s['strategies']['earth']['decision_comparison']['matrix'][0]['discount_rate']=.1
    with pytest.raises(InputError,match='DISCOUNT'):decision_brief(s)


def test_defense_slide_budget_numbers_and_notes():
    from tools.defense import slides_for,n
    s=summary_fixture();slides=slides_for(s)
    assert len(slides)==12
    assert sum(x['seconds'] for x in slides)==420
    assert all(x['notes'] and x['takeaway'] for x in slides)
    assert slides[3]['rows'][0][1]==n(s['strategies']['earth']['base']['total_cost_mln'])
    assert '8,92%' in slides[7]['takeaway']
    for row, sample in zip(slides[7]['rows'],s['discount_rate_crossover']['samples']):
        assert row[1:3]==[n(sample['earth_pv_mln']),n(sample['lunar_pv_mln'])]


def test_defense_generation_is_deterministic_and_does_not_mutate(tmp_path):
    from tools.defense import write_assets
    s=summary_fixture();before=copy.deepcopy(s)
    write_assets(s,tmp_path/'a');write_assets(s,tmp_path/'b')
    assert s==before
    a={p.name:p.read_bytes() for p in (tmp_path/'a').iterdir()}
    b={p.name:p.read_bytes() for p in (tmp_path/'b').iterdir()}
    assert a==b
    assert a['PRESENTATION.html'].count(b'<article ')==8
    assert b'notesToggle' not in a['PRESENTATION.html']
    assert 'TALK_4_MIN.txt' in a


def test_defense_stops_if_control_narrative_becomes_false():
    from tools.defense import slides_for
    s=summary_fixture();s['strategies']['earth']['base']['violations']=1
    with pytest.raises(ValueError,match='NARRATIVE_REVIEW'):slides_for(s)


def test_visual_presentation_keeps_underlying_evidence_and_print_all_slides():
    from tools.defense import slides_for
    from tools.deck_design import render_deck
    s=summary_fixture();slides=slides_for(s);html=render_deck(slides)
    assert slides[4]['visual']['items'][1]['value']==s['strategies']['lunar']['stress']['shortage_t']
    assert len(slides[7]['visual']['points'])==21
    assert 'nextSlide' in html and 'ArrowRight' in html and '@media print' in html
    assert html.count('<article ')==12
    if 'recourse' in s:
        assert slides[8]['visual']['items'][1]['value']==s['recourse'][1]['after']['shortage_t']


def test_deck_has_spoken_story_and_source_driven_four_way_comparison():
    from tools.defense import slides_for
    from tools.deck_design import render_deck
    s=summary_fixture();slides=slides_for(s)
    assert slides[2]['visual']['type']=='process'
    items=slides[6]['visual']['items']
    assert len(items)==4
    for item,source in zip(items,s['strategies']['lunar']['decision_comparison']['matrix']):
        assert item=={'cost':source['total_cost_mln'],'shortage':source['shortage_t'],'violations':source['violations']}
    assert all('ЧТО СКАЗАТЬ' in slide['notes'] and slide['chapter'] for slide in slides)
    html=render_deck(slides)
    assert 'slidePicker' in html
    assert 'speakerPanel' not in html and 'notesToggle' not in html


def test_four_minute_deck_shows_stack_and_calculator_without_prompts():
    from tools.talk import short_defense
    from tools.deck_design import render_deck
    slides=short_defense(summary_fixture())
    assert len(slides)==8 and sum(s['seconds'] for s in slides)==240
    assert slides[2]['visual']['type']=='lab'
    assert 'FastAPI' in str(slides[1])
    rendered=render_deck(slides)
    assert 'Что говорить' not in rendered and 'data-note=' not in rendered
