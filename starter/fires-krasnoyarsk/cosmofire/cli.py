"""CLI: прогон демо-сцены, расчёт метрик, выгрузка артефактов и отчёта."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from cosmofire.burnscar import dice, iou, map_burn_scar
from cosmofire.cluster import cluster_detections, cluster_summary
from cosmofire.filter import FalsePositiveModel
from cosmofire.metrics import area_metrics, cluster_metrics, point_metrics
from cosmofire.synthetic import (
    SceneConfig,
    generate_active_fire_labels,
    generate_burn_scar_scene,
    generate_thermal_anomalies,
)


def run_demo(out_dir: Path, radius_km: float = 12.0) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    model = FalsePositiveModel()

    dets = generate_thermal_anomalies(SceneConfig())
    proba = model.predict_proba(dets)
    pred = (proba >= model.threshold).astype(int)
    kept = dets[pred == 1].copy()
    kept["p_fire"] = proba[pred == 1].round(3)

    clustered = cluster_detections(kept, radius_km=radius_km)
    fires = cluster_summary(clustered)
    if not fires.empty:
        fires["priority"] = (fires["frp_sum"] * (0.5 + fires["confidence"])).round(1)

    scene = generate_burn_scar_scene()
    burn = map_burn_scar(scene["nbr_pre"], scene["nbr_post"], float(scene["pixel_size_m"]))
    truth_ha = float(np.count_nonzero(scene["burn_mask"]) * float(scene["pixel_size_m"]) ** 2 / 10_000.0)

    truth_sites = generate_active_fire_labels(dets[dets["is_fire"] == 1].copy())
    report = {
        "scene": {"n_detections": int(len(dets)), "n_fire_detections": int(dets["is_fire"].sum())},
        "filter": point_metrics(dets["is_fire"].to_numpy(), pred),
        "clusters": {
            **cluster_metrics(truth_sites, fires, radius_km=radius_km),
            "n_fires": int(len(fires)),
        },
        "burn_scar": {
            **area_metrics(burn["area_ha"]["burned_total"], truth_ha),
            "iou": round(iou(burn["severity"] > 0, scene["burn_mask"]), 4),
            "dice": round(dice(burn["severity"] > 0, scene["burn_mask"]), 4),
            "area_by_class_ha": burn["area_ha"],
        },
    }

    dets.to_csv(out_dir / "detections.csv", index=False)
    kept.to_csv(out_dir / "detections_filtered.csv", index=False)
    if not fires.empty:
        fires.to_csv(out_dir / "fires.csv", index=False)
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "explain.json").write_text(
        json.dumps(model.explain(kept, top_k=5), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Фигуры для README и презентации
    try:
        from cosmofire.plots import plot_burnscar, plot_quality, plot_scene_map

        plot_scene_map(dets, fires, path=out_dir / "scene_map.png")
        plot_burnscar(path=out_dir / "burnscar.png")
        plot_quality(report, path=out_dir / "quality.png")
    except Exception as exc:  # pragma: no cover - графика не критична для пайплайна
        print(f"[warn] фигуры не построены: {exc}", file=sys.stderr)

    np.save(out_dir / "severity_map.npy", burn["severity"])
    try:  # tifffile может отсутствовать — тогда остаётся .npy
        import tifffile

        tifffile.imwrite(out_dir / "severity_map.tif", burn["severity"])
    except Exception:  # pragma: no cover
        pass

    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cosmofire", description="КосмоФАЙР: мониторинг лесных пожаров")
    sub = ap.add_subparsers(dest="cmd", required=True)
    demo = sub.add_parser("demo", help="прогнать демо-сцену и сохранить артефакты")
    demo.add_argument("--out", default="data", help="каталог для артефактов")
    demo.add_argument("--radius-km", type=float, default=12.0)
    exp = sub.add_parser("explain", help="показать разбор топ-детекций")
    exp.add_argument("--top", type=int, default=8)
    args = ap.parse_args(argv)

    if args.cmd == "demo":
        report = run_demo(Path(args.out), radius_km=args.radius_km)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.cmd == "explain":
        dets = generate_thermal_anomalies(SceneConfig())
        model = FalsePositiveModel()
        for row in model.explain(dets, top_k=args.top):
            print(f"{row['id']}  p={row['p_fire']:.3f}  {row['decision']}  @ ({row['lat']:.3f}, {row['lon']:.3f})")
            print(f"    признаки: {row['fields']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
