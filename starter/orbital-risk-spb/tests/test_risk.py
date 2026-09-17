import numpy as np

from cosmorisk.metrics import dose_budget, event_metrics, lead_time_hours
from cosmorisk.risk import (
    EVA_DOSE_LIMIT_MSV,
    RiskWeights,
    compute_risk,
    find_windows,
    recommend,
    risk_class,
)
from cosmorisk.synthetic import WeatherConfig, generate_eva_windows, generate_space_weather


def test_series_shape_and_ranges():
    sw = generate_space_weather(WeatherConfig(hours=72, seed=3))
    assert len(sw) == 72
    assert sw["kp"].between(0, 9).all()
    assert sw["proton_flux_10mev"].min() > 0
    assert set(sw["flare_class"]).issubset(set("ABCMX"))


def test_risk_reacts_to_storm():
    sw = generate_space_weather(WeatherConfig(hours=48, n_storms=1, n_spe=1, n_flares=0, seed=11))
    risk = compute_risk(sw)
    assert risk["risk_index"].between(0, 1).all()
    assert risk["risk_index"].max() > 0.4  # в ряду есть буря/SPE
    assert risk["eva_allowed"].any()  # но есть и спокойные окна


def test_windows_and_recommendation():
    sw = generate_space_weather(WeatherConfig(hours=168, seed=5))
    risk = compute_risk(sw)
    windows = find_windows(risk, min_hours=2)
    assert windows and all(w["hours"] >= 2 for w in windows)
    rec = recommend(risk)
    assert rec["current_class"] in {"низкий", "умеренный", "повышенный", "высокий", "критический"}
    assert isinstance(rec["eva_allowed_now"], bool)
    assert len(rec["next_windows"]) <= 3


def test_dose_limit_logic():
    sw = generate_space_weather(WeatherConfig(hours=168, seed=9))
    risk = compute_risk(sw, RiskWeights())
    hard = risk[risk["dose_eva_msv"] >= EVA_DOSE_LIMIT_MSV]
    assert (hard["eva_allowed"] == False).all()  # noqa: E712


def test_metrics_and_custom_threshold():
    risk = compute_risk(generate_space_weather(WeatherConfig(hours=96, seed=2)))
    truth = ~generate_eva_windows(WeatherConfig(hours=96, seed=2)).to_numpy()
    pred = ~risk["eva_allowed"].to_numpy()
    m = event_metrics(truth, pred)
    assert 0 <= m["f1"] <= 1 and m["csi"] <= m["recall"] + 1e-9
    assert lead_time_hours(truth, pred) is None or lead_time_hours(truth, pred) >= 0
    assert dose_budget(0.5)["exceeded"] is False
    strict = compute_risk(generate_space_weather(WeatherConfig(hours=96, seed=2)), RiskWeights(threshold=0.05))
    assert (~strict["eva_allowed"]).sum() >= (~risk["eva_allowed"]).sum()


def test_risk_class_monotone():
    assert risk_class(0.05) == "низкий"
    assert risk_class(0.9) == "критический"


def test_service_endpoints():
    from fastapi.testclient import TestClient

    from cosmorisk.service import app

    client = TestClient(app)
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/risk").json()
    assert client.get("/api/windows").json()
    assert "current_risk_index" in client.get("/api/recommend").json()
    body = {
        "series": [
            {"time": "2026-09-18T00:00:00Z", "kp": 7.0, "dst": -150, "proton_flux_10mev": 250.0, "xray_flux": 2e-4},
            {"time": "2026-09-18T01:00:00Z", "kp": 2.0, "dst": -5, "proton_flux_10mev": 0.3, "xray_flux": 1e-7},
        ]
    }
    r = client.post("/api/assess", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["recommendation"]["current_risk_index"] >= 0
