import io
from functools import lru_cache
import tempfile
import zipfile
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from jsonschema import ValidationError
from .io import ROOT, load_case, load_scenario, export_result
from .engine import evaluate
from .planning import make_plan
from .datasets import research_copy
from .project import calculate_project
from .analysis import sensitivity, risk_analysis, monte_carlo, parameter_sensitivity, compare_decisions, stress_attribution, extension_demo
from .validation import InputError
from .recourse import emergency_response

app = FastAPI(title='Топливный космоконтур 2035', version='0.2.0')

app.mount('/assets', StaticFiles(directory=ROOT/'web'), name='assets')

class Request(BaseModel):
    plan: dict
    scenario_id: str = 'BASE'
    research_scenario: dict | None = None
    count: int = Field(default=100, ge=1, le=300)
    seed: int = 2035
    dependence: str = 'independent'
    research_case_patch: dict | None = None
    alternative_plan: dict | None = None


def scenario(req):
    if req.research_scenario is not None:
        s = req.research_scenario
        if not s.get('scenario_id', '').startswith('TEAM_') or s.get('status') != 'TEAM_ASSUMPTION':
            raise InputError('Research scenarios require TEAM_ ID and TEAM_ASSUMPTION status')
        return s
    if req.scenario_id not in ['BASE', 'MANDATORY_STRESS']:
        raise InputError('Unknown control scenario')
    return load_scenario(req.scenario_id)


def request_case(req):
    case = load_case()
    if req.research_case_patch is not None:
        if req.research_scenario is None:
            raise InputError('RESEARCH_COPY_REQUIRES_TEAM_SCENARIO')
        scenario(req)  # Enforce TEAM namespace and status.
        return research_copy(case, req.research_case_patch)
    return case

def guarded(fn):
    try:
        return fn()
    except (InputError, ValidationError, ValueError, KeyError, TypeError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

@app.get('/')
def index():
    return FileResponse(ROOT/'web/showcase.html')

@app.get('/api/case')
def case_data():
    return {'case': load_case(), 'reference_status': 'BLOCKED: upstream missing docs/ERRATA_AND_PROVENANCE.md',
            'pdf_status': 'All three orbit PDFs reviewed; audit: docs/PDF_AUDIT.md'}

@app.get('/api/plans/{strategy}')
def initial_plan(strategy: str):
    if strategy not in ['earth', 'lunar', 'earth-stress', 'lunar-stress']:
        raise HTTPException(404, 'Unknown plan')
    return make_plan(load_case(), strategy.split('-')[0], load_scenario('MANDATORY_STRESS') if strategy.endswith('-stress') else None)

@app.post('/api/run')
def run(req: Request):
    return guarded(lambda: evaluate(request_case(req), req.plan, scenario(req)))

@app.post('/api/analysis/{kind}')
def analysis(kind: str, req: Request):
    def calculate():
        c = request_case(req)
        if kind == 'sensitivity': return sensitivity(c, req.plan)
        if kind == 'monte-carlo': return monte_carlo(c, req.plan, req.count, req.seed, req.dependence)
        if kind == 'parameters': return parameter_sensitivity(c, req.plan)
        if kind == 'attribution': return stress_attribution(c, req.plan, load_scenario('MANDATORY_STRESS'))
        if kind == 'extension': return extension_demo(c, req.plan)
        if kind == 'adaptation':
            if req.alternative_plan is None:
                raise InputError('ALTERNATIVE_PLAN_REQUIRED')
            return compare_decisions(c, req.plan, req.alternative_plan, load_scenario('BASE'), load_scenario('MANDATORY_STRESS'))
        if kind == 'risks': return risk_analysis(c, req.plan, evaluate(c, req.plan, load_scenario('BASE'), trace=False))
        raise InputError('Unknown analysis')
    return guarded(calculate)

@app.post('/api/export')
def export(req: Request):
    def calculate():
        c = request_case(req)
        result = calculate_project(c, req.plan, scenario(req))
        with tempfile.TemporaryDirectory() as directory:
            export_result(result, directory)
            if req.alternative_plan is not None:
                from .io import save_json, export_table
                comparison = compare_decisions(c, req.plan, req.alternative_plan, load_scenario('BASE'), load_scenario('MANDATORY_STRESS'))
                save_json(Path(directory)/'decision_comparison.json', comparison)
                export_table(Path(directory)/'decision_comparison.csv', comparison['matrix'])
                export_table(Path(directory)/'decision_changes.csv', comparison['changes'])
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                for p in sorted(Path(directory).rglob('*')):
                    if p.is_file(): archive.write(p, p.relative_to(directory).as_posix())
            return Response(stream.getvalue(), media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="fuel-export.zip"'})
    return guarded(calculate)


class RecourseRequest(BaseModel):
    plan: dict
    event_year: int = Field(default=2038, ge=2038, le=2040)
    delivery_share: float = Field(default=0., ge=0, le=1)
    observed_after_days: int = Field(default=0, ge=0, le=364)
    max_emergency_t: float = Field(default=80., ge=0, le=80)


@app.post('/api/recourse')
def recourse(req: RecourseRequest):
    return guarded(lambda: emergency_response(load_case(), **req.model_dump()))


@app.get('/planner')
def planner():
    return FileResponse(ROOT/'web/index.html')


@app.get('/presentation')
def presentation():
    return FileResponse(ROOT/'docs/PRESENTATION.html')


@app.get('/materials/{name}')
def material(name: str):
    allowed = {'REPORT.pdf','COMPARISON.pdf','PRESENTATION.pdf','PRESENTATION.pptx',
               'DEFENSE_GUIDE.md','SPEAKER_NOTES.md','RECOURSE.md'}
    if name not in allowed or not (ROOT/'docs'/name).is_file():
        raise HTTPException(404, 'Unknown material')
    return FileResponse(ROOT/'docs'/name, filename=name)


@app.get('/api/showcase')
@lru_cache(maxsize=1)
def showcase():
    case = load_case()
    data = {'case_version':case['version'], 'years':[r['year'] for r in case['demand']],
            'sources':case['supply_sources'], 'architectures':{},
            'basis':'CASE_INPUT; real rate 0 for this fixed demonstration; edit rate and contracts in /planner',
            'reference_status':'BLOCKED: upstream missing docs/ERRATA_AND_PROVENANCE.md'}
    for architecture in ('earth','lunar'):
        plan = make_plan(case, architecture)
        prepared = make_plan(case, architecture, load_scenario('MANDATORY_STRESS'))
        runs = {}
        for mode, p, scenario_id in [('base',plan,'BASE'),('stress',plan,'MANDATORY_STRESS'),
                                     ('prepared',prepared,'MANDATORY_STRESS'),('prepared_base',prepared,'BASE')]:
            result = evaluate(case, p, load_scenario(scenario_id))
            runs[mode] = {k:result[k] for k in ('plan_id','scenario_id','summary','yearly_balance',
                            'source_schedule','constraint_checks','financial_breakdown')}
            runs[mode]['inventory_trace'] = [r for i,r in enumerate(result['inventory_trace']) if i%7==0 or r['day'] in (1,365)]
        data['architectures'][architecture] = {'plan':plan,'prepared_plan':prepared,'runs':runs}
    return data
