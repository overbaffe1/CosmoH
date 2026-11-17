import pytest
from fuel.engine import balance_step, contract_cost, reserve_required, capacity_check, actual_delivery, throughput_loss
from fuel.io import load_json, REFERENCE


def results():
    c = contract_cost(50, 100, .7, 2, .4)
    b = balance_step(0, 8, 0, 10, 6)
    return {
        'V01': {'closing_inventory_t': balance_step(10, 30, 2, 25, 0)['closing_inventory_t']},
        'V02': {k: b[k] for k in ['served_t', 'shortage_t', 'closing_inventory_t']},
        'V03': {'payable_volume_t': c['payable_volume_t'], 'variable_payment_mln': c['procurement_mln']},
        'V04': {'variable_payment_mln': c['procurement_mln']},
        'V05': {'reservation_payment_mln': contract_cost(0, 100, 0, 2, .4, .5)['reservation_mln']},
        'V06': {'losses_t': throughput_loss(20, .05)},
        'V07': {'reserve_t': reserve_required(365)},
        'V08': capacity_check(12, 10),
        'V09': {'total_demand_t': balance_step(0, 100, 0, 100, 60)['served_t']},
        'V10': {'actual_delivery_t': actual_delivery(20, .5)},
    }

@pytest.mark.parametrize('vector', load_json(REFERENCE/'validation/expected_checks.json'), ids=lambda v: v['case_id'])
def test_official_vector(vector):
    assert results()[vector['case_id']] == pytest.approx(vector['expected']) if vector['case_id'] != 'V08' else results()['V08'] == vector['expected']
