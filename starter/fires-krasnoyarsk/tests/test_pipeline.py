import numpy as np
import pandas as pd

from cosmofire.burnscar import iou, map_burn_scar
from cosmofire.cluster import cluster_detections, cluster_summary
from cosmofire.filter import FalsePositiveModel
from cosmofire.metrics import point_metrics
from cosmofire.synthetic import SceneConfig, generate_burn_scar_scene, generate_thermal_anomalies


def test_synthetic_shape_and_labels():
    dets = generate_thermal_anomalies(SceneConfig(seed=1))
    assert {"lat", "lon", "frp", "brightness", "is_fire"} <= set(dets.columns)
    assert dets["is_fire"].nunique() == 2
    assert len(dets) > 20


def test_filter_beats_random():
    dets = generate_thermal_anomalies(SceneConfig(seed=42))
    model = FalsePositiveModel()
    pred = model.predict(dets)
    m = point_metrics(dets["is_fire"].to_numpy(), pred)
    assert m["f1"] > 0.6, m
    assert m["precision"] > 0.5, m


def test_clustering_separates_sources():
    dets = generate_thermal_anomalies(SceneConfig(n_fires=3, n_industry=0, seed=5))
    cl = cluster_detections(dets, radius_km=12.0, min_samples=2)
    # три компактных источника должны дать не больше 4 очагов
    assert cl["cluster_id"].nunique() <= 4
    summary = cluster_summary(cl)
    assert summary["detections"].sum() == len(dets)


def test_burn_scar_area_reasonable():
    scene = generate_burn_scar_scene(size=128, seed=3)
    res = map_burn_scar(scene["nbr_pre"], scene["nbr_post"], float(scene["pixel_size_m"]))
    truth_px = int(scene["burn_mask"].sum())
    pred_px = int((res["severity"] > 0).sum())
    assert abs(pred_px - truth_px) / max(1, truth_px) < 0.6
    assert 0.0 <= iou(res["severity"] > 0, scene["burn_mask"]) <= 1.0
    assert res["area_ha"]["burned_total"] > 0


def test_service_endpoints():
    from fastapi.testclient import TestClient

    from cosmofire.service import app

    client = TestClient(app)
    assert client.get("/api/health").json()["status"] == "ok"
    fires = client.get("/api/fires").json()
    assert isinstance(fires, list) and fires
    gj = client.get("/api/geojson").json()
    assert gj["type"] == "FeatureCollection"
    body = {
        "detections": [
            {"lat": 56.0, "lon": 92.9, "brightness": 350.0, "frp": 25.0, "daynight": "D", "instrument": "VIIRS"},
            {"lat": 56.02, "lon": 92.92, "brightness": 348.0, "frp": 22.0, "daynight": "D", "instrument": "MODIS"},
        ]
    }
    r = client.post("/api/analyze", json=body)
    assert r.status_code == 200 and r.json()["n_input"] == 2
