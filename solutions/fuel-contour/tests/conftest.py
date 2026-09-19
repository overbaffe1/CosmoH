import pytest
from fuel.io import load_case, load_scenario
from fuel.planning import make_plan

@pytest.fixture
def case():
    return load_case()

@pytest.fixture
def plan(case):
    return make_plan(case)

@pytest.fixture
def base():
    return load_scenario('BASE')
