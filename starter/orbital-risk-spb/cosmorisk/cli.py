"""CLI «КосмоРиск»: прогон ряда, метрики, окна ВКД, отчёт и график."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cosmorisk.metrics import dose_budget, event_metrics, lead_time_hours
from cosmorisk.risk import RiskWeights, compute_risk, find_windows, recommend, risk_class
from cosmorisk.synthetic import WeatherConfig, generate_eva_windows, generate_space_weather


def run_demo(out_dir: Path, threshold: float = 0.45) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    sw = generate_space_weather(WeatherConfig())
    risk = compute_risk(sw, RiskWeights(threshold=threshold))

    truth_bad = ~generate_eva_windows(WeatherConfig()).to_numpy()
    pred_bad = ~risk["eva_allowed"].to_numpy()
    windows = find_windows(risk)
    rec = recommend(risk)
    cum24 = float(risk["dose_eva_msv"].iloc[:24].sum())

    report = {
        "series": {"hours": int(len(risk)), "danger_hours_pred": int(pred_bad.sum())},
        "detection": event_metrics(truth_bad, pred_bad),
        "lead_time_hours": lead_time_hours(truth_bad, pred_bad),
        "dose_budget_24h_msv": dose_budget(cum24, limit_msv=10.0),
        "windows": windows[:10],
        "recommendation": rec,
        "risk_classes": {c: int((risk["risk_index"].map(risk_class) == c).sum()) for c in
                         ["низкий", "умеренный", "повышенный", "высокий", "критический"]},
    }
    risk.to_csv(out_dir / "risk_series.csv", index=False)
    (out_dir / "windows.json").write_text(json.dumps(windows, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        _plot(risk, out_dir / "risk_chart.png")
    except Exception:  # matplotlib может отсутствовать
        pass
    return report


def _plot(risk, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 3.4), dpi=130)
    t = range(len(risk))
    ax.plot(t, risk["risk_index"], color="#4fc3ff", label="индекс риска ВКД")
    ax.axhline(0.45, color="#ff7676", ls="--", lw=1, label="порог 0.45")
    for i, ok in enumerate(risk["eva_allowed"]):
        if not ok:
            ax.axvspan(i - 0.5, i + 0.5, color="#ff7676", alpha=0.12)
    ax2 = ax.twinx()
    ax2.plot(t, risk["dose_eva_msv"], color="#ffd166", lw=1.2, alpha=0.9, label="доза за 7 ч, мЗв")
    ax.set_xlabel("часы от старта ряда")
    ax.set_ylabel("индекс риска")
    ax2.set_ylabel("доза, мЗв")
    ax.set_ylim(0, 1)
    ax.legend(loc="upper left", fontsize=8)
    ax2.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cosmorisk", description="КосмоРиск: риск ВКД")
    sub = ap.add_subparsers(dest="cmd", required=True)
    demo = sub.add_parser("demo", help="прогнать демо-ряд и сохранить артефакты")
    demo.add_argument("--out", default="data")
    demo.add_argument("--threshold", type=float, default=0.45)
    args = ap.parse_args(argv)

    if args.cmd == "demo":
        print(json.dumps(run_demo(Path(args.out), args.threshold), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
