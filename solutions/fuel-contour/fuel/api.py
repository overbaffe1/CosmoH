import io
import tempfile
import zipfile
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from jsonschema import ValidationError
from .io import ROOT, load_case, load_scenario, export_result
from .engine import evaluate
from .planning import make_plan
from .analysis import sensitivity, risk_analysis, monte_carlo
from .validation import InputError

app = FastAPI(title='Топливный космоконтур 2035', version='0.1.0')

class Request(BaseModel):
    plan: dict
    scenario_id: str = 'BASE'
    research_scenario: dict | None = None
    count: int = Field(default=100, ge=1, le=300)
    seed: int = 2035


def scenario(req):
    if req.research_scenario is not None:
        s = req.research_scenario
        if not s.get('scenario_id', '').startswith('TEAM_') or s.get('status') != 'TEAM_ASSUMPTION':
            raise InputError('Research scenarios require TEAM_ ID and TEAM_ASSUMPTION status')
        return s
    if req.scenario_id not in ['BASE', 'MANDATORY_STRESS']:
        raise InputError('Unknown control scenario')
    return load_scenario(req.scenario_id)


def guarded(fn):
    try:
        return fn()
    except (InputError, ValidationError, ValueError, KeyError, TypeError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

@app.get('/')
def index():
    return FileResponse(ROOT/'web/index.html')

@app.get('/api/case')
def case_data():
    return {'case': load_case(), 'reference_status': 'BLOCKED: upstream missing docs/ERRATA_AND_PROVENANCE.md',
            'pdf_status': 'overbaffe1/orbit returned 404; three PDFs not reviewed'}

@app.get('/api/plans/{strategy}')
def initial_plan(strategy: str):
    if strategy not in ['earth', 'lunar']:
        raise HTTPException(404, 'Unknown plan')
    return make_plan(load_case(), strategy)

@app.post('/api/run')
def run(req: Request):
    return guarded(lambda: evaluate(load_case(), req.plan, scenario(req)))

@app.post('/api/analysis/{kind}')
def analysis(kind: str, req: Request):
    def calculate():
        c = load_case()
        if kind == 'sensitivity': return sensitivity(c, req.plan)
        if kind == 'monte-carlo': return monte_carlo(c, req.plan, req.count, req.seed)
        if kind == 'risks': return risk_analysis(c, req.plan, evaluate(c, req.plan, load_scenario('BASE'), trace=False))
        raise InputError('Unknown analysis')
    return guarded(calculate)

@app.post('/api/export')
def export(req: Request):
    def calculate():
        c = load_case()
        result = evaluate(c, req.plan, scenario(req))
        result['risk_register'] = risk_analysis(c, req.plan, evaluate(c, req.plan, load_scenario('BASE'), trace=False))
        with tempfile.TemporaryDirectory() as directory:
            export_result(result, directory)
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                for p in sorted(Path(directory).iterdir()): archive.write(p, p.name)
            return Response(stream.getvalue(), media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="fuel-export.zip"'})
    return guarded(calculate)
