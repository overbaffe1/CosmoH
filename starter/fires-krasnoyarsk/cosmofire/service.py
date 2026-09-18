"""FastAPI-сервис оперативного мониторинга пожаров + демонстрационная карта.

Эндпоинты:
  GET  /                     — веб-карта (оффлайн, без CDN и тайлов)
  GET  /api/health           — проба живости
  GET  /api/detections       — тепловые аномалии с вероятностью «пожар»
  GET  /api/fires            — очаги (кластеры) с приоритетом
  GET  /api/geojson          — GeoJSON для ГИС-клиентов
  GET  /api/burnscar         — площади гари по классам тяжести
  GET  /api/metrics          — метрики качества на валидационной сцене
  POST /api/analyze          — принять свои точки (JSON) и вернуть разбор

Всё считается локально; сеть не требуется.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from cosmofire.burnscar import map_burn_scar
from cosmofire.cluster import cluster_detections, cluster_summary
from cosmofire.filter import FalsePositiveModel
from cosmofire.metrics import area_metrics, cluster_metrics, point_metrics
from cosmofire.synthetic import (
    SceneConfig,
    generate_active_fire_labels,
    generate_burn_scar_scene,
    generate_thermal_anomalies,
)

app = FastAPI(title="КосмоФАЙР — оперативный мониторинг пожаров", version="0.1.0")
_model = FalsePositiveModel()


@lru_cache(maxsize=1)
def _analysis() -> dict[str, Any]:
    """Один раз считаем демо-сцену: детекции -> фильтр -> кластеры -> гари -> метрики."""

    dets = generate_thermal_anomalies(SceneConfig())
    proba = _model.predict_proba(dets)
    pred = (proba >= _model.threshold).astype(int)
    kept = dets[pred == 1].copy()
    kept["p_fire"] = proba[pred == 1]

    clustered = cluster_detections(kept)
    fires = cluster_summary(clustered)
    if not fires.empty:
        # Приоритет = FRP * уверенность * свежесть (демо: свежесть не учитываем).
        fires["priority"] = (fires["frp_sum"] * (0.5 + fires["confidence"])).round(1)
        fires = fires.sort_values("priority", ascending=False).reset_index(drop=True)

    scene = generate_burn_scar_scene()
    burn = map_burn_scar(scene["nbr_pre"], scene["nbr_post"], float(scene["pixel_size_m"]))
    truth_ha = float(np.count_nonzero(scene["burn_mask"]) * (float(scene["pixel_size_m"]) ** 2) / 10_000.0)

    pm = point_metrics(dets["is_fire"].to_numpy(), pred)
    truth_sites = generate_active_fire_labels(dets[dets["is_fire"] == 1].copy())
    cm = cluster_metrics(truth_sites, fires)
    am = area_metrics(burn["area_ha"]["burned_total"], truth_ha)

    return {
        "detections": dets,
        "kept": kept,
        "proba": proba,
        "fires": fires,
        "burn": burn,
        "scene": scene,
        "metrics": {"point": pm, "cluster": cm, "area": am},
    }


class AnalyzeRequest(BaseModel):
    detections: list[dict]
    radius_km: float = Field(default=12.0, ge=1.0, le=50.0)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/detections")
def detections(only_fire: bool = False) -> list[dict]:
    data = _analysis()
    dets = data["kept"] if only_fire else data["detections"]
    proba = data["proba"]
    out = dets.copy()
    out["p_fire"] = proba if only_fire else proba[dets.index]
    out["p_fire"] = out["p_fire"].round(3)
    return out.replace({np.nan: None}).to_dict(orient="records")


@app.get("/api/fires")
def fires() -> list[dict]:
    return _analysis()["fires"].replace({np.nan: None}).to_dict(orient="records")


@app.get("/api/metrics")
def metrics() -> dict:
    return _analysis()["metrics"]


@app.get("/api/burnscar")
def burnscar() -> dict:
    data = _analysis()
    sev = data["burn"]["severity"]
    return {
        "shape": list(sev.shape),
        "area_ha": data["burn"]["area_ha"],
        "mean_dnbr": round(data["burn"]["mean_dnbr"], 3),
        "max_dnbr": round(data["burn"]["max_dnbr"], 3),
        "severity_map": sev.tolist(),
    }


@app.get("/api/geojson")
def geojson() -> dict:
    data = _analysis()
    features: list[dict] = []
    for _, r in data["kept"].iterrows():
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]},
                "properties": {
                    "kind": "detection",
                    "satellite": r["satellite"],
                    "instrument": r["instrument"],
                    "brightness": float(r["brightness"]),
                    "frp": float(r["frp"]),
                    "acq_time": str(r["acq_time"]),
                },
            }
        )
    for _, r in data["fires"].iterrows():
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]},
                "properties": {
                    "kind": "fire",
                    "detections": int(r["detections"]),
                    "frp_sum": float(r["frp_sum"]),
                    "confidence": float(r["confidence"]),
                    "priority": float(r["priority"]),
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    if not req.detections:
        raise HTTPException(status_code=400, detail="Пустой список детекций")
    needed = {"lat", "lon", "brightness", "frp", "daynight", "instrument"}
    missing = needed - set(req.detections[0].keys())
    if missing:
        raise HTTPException(status_code=422, detail=f"Нет обязательных полей: {sorted(missing)}")
    dets = pd.DataFrame(req.detections)
    if "satellite" not in dets.columns:
        dets["satellite"] = "unknown"
    p = _model.predict_proba(dets)
    dets["p_fire"] = p.round(3)
    kept = dets[p >= _model.threshold]
    clustered = cluster_detections(kept, radius_km=req.radius_km) if not kept.empty else kept
    summary = cluster_summary(clustered) if not kept.empty else pd.DataFrame()
    return {
        "n_input": int(len(dets)),
        "n_fire": int(len(kept)),
        "explanation": _model.explain(dets),
        "fires": summary.replace({np.nan: None}).to_dict(orient="records"),
    }


_PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>КосмоФАЙР — мониторинг лесных пожаров</title>
<style>
 body{font-family:system-ui,Segoe UI,Roboto,sans-serif;margin:0;background:#0e1116;color:#e6edf3}
 header{padding:14px 20px;background:#151b23;border-bottom:1px solid #2a3441;display:flex;gap:20px;align-items:baseline}
 h1{font-size:18px;margin:0}
 .muted{color:#93a4b8;font-size:13px}
 main{display:grid;grid-template-columns:1fr 380px;gap:16px;padding:16px}
 .card{background:#151b23;border:1px solid #2a3441;border-radius:10px;padding:12px}
 table{width:100%;border-collapse:collapse;font-size:13px}
 th,td{text-align:left;padding:5px 6px;border-bottom:1px solid #222c38}
 th{color:#93a4b8;font-weight:600}
 .pill{display:inline-block;padding:1px 7px;border-radius:20px;font-size:11px}
 .hi{background:#3d1d1d;color:#ff9c9c}.lo{background:#1d2f3d;color:#9cd2ff}
 #map{width:100%;height:520px;background:#0b0f14;border-radius:8px}
 #sev{image-rendering:pixelated;width:100%;border-radius:8px}
</style></head><body>
<header><h1>🛰 КосмоФАЙР</h1><span class="muted">оперативный мониторинг лесных пожаров · демо-сцена (синтетика)</span></header>
<main>
 <div>
  <div class="card"><div class="muted" style="margin-bottom:8px">Карта тепловых аномалий и очагов (клик по очагу — детали)</div>
   <div id="map"></div></div>
  <div class="card" style="margin-top:16px"><div class="muted" style="margin-bottom:8px">Карта гари Sentinel-2 (dNBR)</div>
   <img id="sev" alt="severity map"></div>
 </div>
 <div>
  <div class="card" id="metrics"></div>
  <div class="card" style="margin-top:16px"><div class="muted" style="margin-bottom:8px">Очаги по приоритету</div>
   <div id="fires"></div></div>
 </div>
</main>
<script>
const S = {minLat:99,maxLat:-99,minLon:999,maxLon:-999};
function proj(lat,lon,w,h){
  if(S.maxLat-S.minLat<1e-6){S.minLat-=1;S.maxLat+=1;S.minLon-=1;S.maxLon+=1;}
  const x=(lon-S.minLon)/(S.maxLon-S.minLon)*w, y=h-(lat-S.minLat)/(S.maxLat-S.minLat)*h;
  return [x,y];
}
async function main(){
  const [dets,fires,met,burn] = await Promise.all([
    fetch('api/detections').then(r=>r.json()),
    fetch('api/fires').then(r=>r.json()),
    fetch('api/metrics').then(r=>r.json()),
    fetch('api/burnscar').then(r=>r.json())]);
  [...dets,...fires].forEach(d=>{S.minLat=Math.min(S.minLat,d.lat);S.maxLat=Math.max(S.maxLat,d.lat);
    S.minLon=Math.min(S.minLon,d.lon);S.maxLon=Math.max(S.maxLon,d.lon);});
  const padLat=(S.maxLat-S.minLat)*0.06, padLon=(S.maxLon-S.minLon)*0.06;
  S.minLat-=padLat;S.maxLat+=padLat;S.minLon-=padLon;S.maxLon+=padLon;
  const w=760,h=520,s=document.getElementById('map');
  let svg=`<svg viewBox="0 0 ${w} ${h}" width="100%" height="100%">`;
  svg+=`<rect width="${w}" height="${h}" fill="#0b0f14"/>`;
  for(let i=1;i<9;i++){const x=i*w/9,y=i*h/9;
    svg+=`<line x1="${x}" y1="0" x2="${x}" y2="${h}" stroke="#141c25"/><line x1="0" y1="${y}" x2="${w}" y2="${y}" stroke="#141c25"/>`;}
  dets.forEach(d=>{const [x,y]=proj(d.lat,d.lon,w,h);const fp=d.p_fire>=0.5;
    svg+=`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${fp?2.4:1.6}" fill="${fp?'#ff6b4a':'#5b6b7d'}" opacity="${fp?0.95:0.6}"><title>${d.satellite} ${d.acq_time} · FRP ${d.frp} МВт · p(пожар)=${d.p_fire}</title></circle>`;});
  fires.forEach(f=>{const [x,y]=proj(f.lat,f.lon,w,h);const r=6+Math.min(18,Math.sqrt(f.frp_sum)/1.5);
    svg+=`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r.toFixed(1)}" fill="#ff2d1a" opacity="0.16"/>`;
    svg+=`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.2" fill="none" stroke="#ffb03a" stroke-width="1.6"><title>Очаг: ${f.detections} детекций, FRP ∑ ${f.frp_sum.toFixed(0)} МВт, уверенность ${f.confidence}, приоритет ${f.priority}</title></circle>`;});
  svg+='</svg>'; s.innerHTML=svg;
  const sev=burn.severity_map, H=sev.length, W=sev[0].length;
  const c=document.createElement('canvas');c.width=W;c.height=H;const ctx=c.getContext('2d');
  const img=ctx.createImageData(W,H);const pal={0:[11,15,20,255],1:[74,124,74,255],2:[214,168,58,255],3:[214,72,45,255]};
  for(let y=0;y<H;y++)for(let x=0;x<W;x++){const v=pal[sev[y][x]]||pal[0];const i=(y*W+x)*4;
    img.data[i]=v[0];img.data[i+1]=v[1];img.data[i+2]=v[2];img.data[i+3]=v[3];}
  ctx.putImageData(img,0,0);document.getElementById('sev').src=c.toDataURL();
  const m=met;
  document.getElementById('metrics').innerHTML=`<div class="muted" style="margin-bottom:8px">Качество</div>
   <table><tr><th>Точки (детекции)</th><th>Очаги</th></tr>
   <tr><td>precision <b>${m.point.precision}</b></td><td>precision <b>${m.cluster.site_precision}</b></td></tr>
   <tr><td>recall <b>${m.point.recall}</b></td><td>recall <b>${m.cluster.site_recall}</b></td></tr>
   <tr><td>F1 <b>${m.point.f1}</b></td><td>ср. ошибка локализации <b>${m.cluster.mean_loc_error_km} км</b></td></tr></table>
   <div class="muted" style="margin-top:8px">Площадь гари: прогноз ${m.area.pred_ha} га против эталона ${m.area.truth_ha} га (ошибка ${(m.area.rel_error*100).toFixed(1)}%)</div>`;
  document.getElementById('fires').innerHTML='<table><tr><th>№</th><th>Ш,Д</th><th>Детекций</th><th>FRP ∑</th><th>Приоритет</th></tr>'+
   fires.map((f,i)=>`<tr><td>${i+1}</td><td>${f.lat.toFixed(2)}, ${f.lon.toFixed(2)} <span class="pill ${f.confidence>0.5?'hi':'lo'}">${f.confidence}</span></td><td>${f.detections}</td><td>${f.frp_sum.toFixed(0)}</td><td>${f.priority}</td></tr>`).join('')+'</table>';
}
main();
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _PAGE


@app.post("/api/reload", include_in_schema=False)
def reload_cache() -> dict[str, str]:
    _analysis.cache_clear()
    return {"status": "cache cleared"}
