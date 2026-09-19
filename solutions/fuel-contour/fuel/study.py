"""Bounded parameter study, not probabilities, optimization or a new response policy."""
from .recourse import emergency_response
from .io import digest

DELIVERY_SHARES = (0., .25, .5, .75, 1.)
DELAYS = (0, 30, 60, 90, 180, 270, 330)


def response_grid(case, plan, shares=DELIVERY_SHARES, delays=DELAYS):
    if not shares or not delays or len(set(shares)) != len(shares) or len(set(delays)) != len(delays):
        raise ValueError('STUDY_GRID: nonempty unique axes required')
    rows=[]
    for share in shares:
        for delay in delays:
            r=emergency_response(case,plan,event_year=2038,delivery_share=share,
                                 observed_after_days=delay,max_emergency_t=80.)
            rows.append({'delivery_share':share,'observed_after_days':delay,
                         'before':r['before']['summary'],'after':r['after']['summary'],
                         'added_order_t':r['added_order_t'],'incremental_cost_mln':r['incremental_cost_mln'],
                         'action':r['action'],'residual_failed_rules':r['residual_failed_rules'],
                         'prefix_unchanged':r['prefix_unchanged_until_arrival'],
                         'commitments_unchanged':r['original_commitments_unchanged'],
                         'response_sha256':digest(r)})
    return {'status':'TEAM_ASSUMPTION','case_sha256':digest(case),'plan_sha256':digest(plan),
            'plan_id':plan['plan_id'],'event_year':2038,'max_emergency_t':80.,
            'delivery_shares':list(shares),'observation_delays':list(delays),'rows':rows,
            'method':'Cartesian sensitivity grid of the same fixed Emergency policy, not a distribution or optimization.',
            'limits':['Delivery fraction 0..1 is a physical fraction; 1 is the no-event control, not a recovery success.',
                      'Quarter steps sample severity; delays sample information latency. No frequency or likelihood is implied.',
                      'Annual outage starts on day one; residual delivery fraction is announced at observation.',
                      'Original commitments remain locked; free Emergency contract, tariff and financing are assumptions.',
                      'Same 2038 event and initial Lunar plan in every cell, not MANDATORY_STRESS.',
                      'Feasibility applies only at sampled points; no interpolation or continuous boundary is proved.']}
