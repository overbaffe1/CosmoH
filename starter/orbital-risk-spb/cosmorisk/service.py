"""FastAPI-сервис «КосмоРиск»: индекс риска ВКД, окна безопасности, доза.

Эндпоинты:
  GET  /                — дашборд (графики риска и окна ВКД, оффлайн)
  GET  /api/health
  GET  /api/weather     — ряд космической погоды
  GET  /api/risk        — индекс риска и доза за ВКД
  GET  /api/windows     — безопасные окна
  GET  /api/recommend   — оперативная рекомендация «сейчас»
  GET  /api/metrics     — качество детекции опасных периодов
  POST /api/assess      — оценка риска по своим данным (ряд в JSON)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from cosmorisk.metrics import dose_budget, event_metrics, lead_time_hours
from cosmorisk.risk import TYPICAL_EVA_HOURS, RiskWeights, compute_risk, find_windows, recommend, risk_class
from cosmorisk.synthetic import WeatherConfig, generate_eva_windows, generate_space_weather

app = FastAPI(title="КосмоРиск — риск ВКД по космической погоде", version="0.1.0")


@lru_cache(maxsize=1)
def _risk() -> pd.DataFrame:
    sw = generate_space_weather(WeatherConfig())
    return compute_risk(sw, RiskWeights())


@lru_cache(maxsize=1)
def _metrics() -> dict[str, Any]:
    risk = _risk()
    truth_bad = ~generate_eva_windows(WeatherConfig()).to_numpy()
    pred_bad = ~risk["eva_allowed"].to_numpy()
    cum = float(risk["dose_eva_msv"].iloc[:24].sum())
    return {
        "detection": event_metrics(truth_bad, pred_bad),
        "lead_time_hours": lead_time_hours(truth_bad, pred_bad),
        "dose_budget_24h": dose_budget(cum, limit_msv=10.0),
        "n_danger_hours_truth": int(truth_bad.sum()),
    }


class AssessRequest(BaseModel):
    series: list[dict]
    threshold: float = 0.45


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/weather")
def weather() -> list[dict]:
    return _risk().to_dict(orient="records")


@app.get("/api/risk")
def risk() -> list[dict]:
    cols = ["time", "risk_index", "risk_class", "dose_rate_msv_h", "dose_eva_msv", "eva_allowed"]
    df = _risk().copy()
    df["risk_class"] = df["risk_index"].map(risk_class)
    return df[cols].replace({np.nan: None}).to_dict(orient="records")


@app.get("/api/windows")
def windows() -> list[dict]:
    return find_windows(_risk())


@app.get("/api/recommend")
def recommend_now() -> dict:
    return recommend(_risk())


@app.get("/api/metrics")
def metrics() -> dict:
    return _metrics()


@app.post("/api/assess")
def assess(req: AssessRequest) -> dict:
    if not req.series:
        raise HTTPException(status_code=400, detail="Пустой ряд")
    df = pd.DataFrame(req.series)
    for col in ("kp", "dst", "proton_flux_10mev", "xray_flux"):
        if col not in df.columns:
            raise HTTPException(status_code=422, detail=f"Нет обязательного поля: {col}")
    if "time" not in df.columns:
        df["time"] = pd.date_range("2026-09-18", periods=len(df), freq="h")
    if "flare_class" not in df.columns:
        from cosmorisk.synthetic import _flare_class

        df["flare_class"] = [_flare_class(float(v)) for v in df["xray_flux"]]
    risk_df = compute_risk(df, RiskWeights(threshold=req.threshold))
    rec = recommend(risk_df)
    return {
        "n_points": int(len(risk_df)),
        "typical_eva_hours": TYPICAL_EVA_HOURS,
        "recommendation": rec,
        "danger_hours": int((~risk_df["eva_allowed"]).sum()),
        "windows": find_windows(risk_df)[:5],
    }


_PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>КосмоРиск — ВКД и космическая погода</title>
<style>
 body{font-family:system-ui,Segoe UI,Roboto,sans-serif;margin:0;background:#0e1116;color:#e6edf3}
 header{padding:14px 20px;background:#151b23;border-bottom:1px solid #2a3441}
 h1{font-size:18px;margin:0 0 2px}
 .muted{color:#93a4b8;font-size:13px}
 main{padding:16px;display:grid;gap:16px;grid-template-columns:1fr 1fr}
 .card{background:#151b23;border:1px solid #2a3441;border-radius:10px;padding:14px}
 .big{font-size:34px;font-weight:700}
 table{width:100%;border-collapse:collapse;font-size:13px}
 th,td{text-align:left;padding:5px 6px;border-bottom:1px solid #222c38}
 th{color:#93a4b8}
 .ok{color:#5ddc8a}.bad{color:#ff7676}
 .span2{grid-column:span 2}
</style></head><body>
<header><h1>☀️ КосмоРиск</h1><div class="muted">риск ВКД по космической погоде · демо-ряд (синтетика, 168 ч с шагом 1 ч)</div></header>
<main>
 <div class="card" id="now"></div>
 <div class="card" id="drivers"></div>
 <div class="card span2"><div class="muted" style="margin-bottom:8px">Индекс риска и доза за типовую ВКД (7 ч)</div><div id="chart"></div></div>
 <div class="card span2" id="windows"></div>
 <div class="card span2" id="metrics"></div>
</main>
<script>
function line(series,color,w,h,lo,hi){let p='';series.forEach((v,i)=>{const x=i/(series.length-1)*w,y=h-(v-lo)/(hi-lo)*h;p+=`${i?'L':'M'}${x.toFixed(1)} ${y.toFixed(1)} `;});return `<path d="${p}" fill="none" stroke="${color}" stroke-width="1.6"/>`;}
async function main(){
 const [rec,risk,win,met]=await Promise.all([
  fetch('api/recommend').then(r=>r.json()),
  fetch('api/risk').then(r=>r.json()),
  fetch('api/windows').then(r=>r.json()),
  fetch('api/metrics').then(r=>r.json())]);
 document.getElementById('now').innerHTML=`<div class="muted">Сейчас (${rec.now.slice(0,16).replace('T',' ')})</div>
  <div class="big ${rec.eva_allowed_now?'ok':'bad'}">${rec.current_risk_index} · ${rec.current_class}</div>
  <div>ВКД: <b class="${rec.eva_allowed_now?'ok':'bad'}">${rec.eva_allowed_now?'разрешена':'запрещена'}</b> · доза за 7 ч: <b>${rec.current_dose_eva_msv} мЗв</b> (лимит 1 мЗв)</div>`;
 const d=rec.drivers;
 document.getElementById('drivers').innerHTML=`<div class="muted" style="margin-bottom:8px">Ведущие факторы</div>
  <table><tr><th>Kp</th><td>${d.kp}</td></tr><tr><th>Dst</th><td>${d.dst} нТл</td></tr>
  <tr><th>Протоны >10 МэВ</th><td>${d.proton_flux_10mev.toFixed(2)} pfu</td></tr>
  <tr><th>Вспышка</th><td>${d.flare_class}</td></tr></table>`;
 const w=1100,h=170,ri=risk.map(r=>r.risk_index);
 let svg=`<svg viewBox="0 0 ${w} ${h+20}" width="100%">
  <line x1="0" y1="${h-0.45*h}" x2="${w}" y2="${h-0.45*h}" stroke="#ff7676" stroke-dasharray="4 4"/>
  <text x="4" y="${h-0.45*h-4}" fill="#ff7676" font-size="11">порог риска 0.45</text>`;
 svg+=line(ri,'#4fc3ff',w,h,0,1);
 risk.forEach((r,i)=>{if(!r.eva_allowed){const x=i/(risk.length-1)*w;svg+=`<rect x="${x.toFixed(1)}" y="0" width="${(w/risk.length).toFixed(2)}" height="${h}" fill="#ff7676" opacity="0.18"/>`;}});
 svg+=`</svg><div class="muted">Красным — периоды, когда ВКД запрещена (буря, SPE или превышение дозового лимита)</div>`;
 document.getElementById('chart').innerHTML=svg;
 document.getElementById('windows').innerHTML=`<div class="muted" style="margin-bottom:8px">Ближайшие безопасные окна</div>
  <table><tr><th>С</th><th>По</th><th>Часов</th><th>Макс. риск</th><th>Макс. доза за 7 ч, мЗв</th></tr>`+
  (rec.next_windows.length?rec.next_windows.map(x=>`<tr><td>${x.from.slice(0,16).replace('T',' ')}</td><td>${x.to.slice(5,16).replace('T',' ')}</td><td>${x.hours}</td><td>${x.max_risk_index}</td><td>${x.max_dose_eva_msv}</td></tr>`).join(''):'<tr><td colspan="5">Ближайшие 3 суток — окна короче 3 ч</td></tr>')+`</table>
  <div class="muted" style="margin-top:6px">Всего окон в ряду: ${win.length}</div>`;
 const m=met.detection;
 document.getElementById('metrics').innerHTML=`<div class="muted" style="margin-bottom:8px">Качество детекции опасных периодов (часовой шаг)</div>
  <table><tr><th>precision</th><th>recall</th><th>F1</th><th>CSI</th><th>Заблаговременность</th></tr>
  <tr><td>${m.precision}</td><td>${m.recall}</td><td>${m.f1}</td><td>${m.csi}</td><td>${met.lead_time_hours} ч</td></tr></table>
  <div class="muted" style="margin-top:6px">Опасных часов по эталону: ${met.n_danger_hours_truth}; запас дозы за первые сутки: ${met.dose_budget_24h.cumulative_msv} мЗв</div>`;
}
main();
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _PAGE
