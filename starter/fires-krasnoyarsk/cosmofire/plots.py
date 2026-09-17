"""Фигуры для отчёта и презентации (matplotlib, без интерактива).

Используются шрифты DejaVu из комплекта matplotlib — кириллица работает оффлайн.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cosmofire.burnscar import SEVERITY_LABELS, map_burn_scar  # noqa: E402

plt.rcParams.update({"font.size": 10, "figure.dpi": 140, "axes.grid": True, "grid.alpha": 0.25})


def plot_scene_map(dets: pd.DataFrame, fires: pd.DataFrame, kept_ids: set | None = None, path: Path | str = "scene_map.png") -> Path:
    fig, ax = plt.subplots(figsize=(9, 5.2))
    is_fire = dets["is_fire"] == 1 if "is_fire" in dets.columns else dets["p_fire"] >= 0.5
    ax.scatter(dets.loc[~is_fire, "lon"], dets.loc[~is_fire, "lat"], s=18, c="#5b6b7d", label="промышленный источник (ложное)", zorder=2)
    ax.scatter(dets.loc[is_fire, "lon"], dets.loc[is_fire, "lat"], s=22, c="#ff6b4a", label="тепловая аномалия (пожар)", zorder=3)
    if not fires.empty:
        sizes = 40 + 12 * np.sqrt(fires["frp_sum"])
        ax.scatter(fires["lon"], fires["lat"], s=sizes, facecolors="none", edgecolors="#ffb03a", linewidths=1.6,
                   label="очаг (кластер)", zorder=4)
        for _, r in fires.iterrows():
            ax.annotate(f"FRP {r['frp_sum']:.0f}", (r["lon"], r["lat"]), textcoords="offset points",
                        xytext=(6, 6), fontsize=8, color="#ffd166")
    ax.set_xlabel("долгота, °")
    ax.set_ylabel("широта, °")
    ax.set_title("Тепловые аномалии и очаги пожаров (демо-сцена)")
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    path = Path(path)
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_burnscar(size: int = 256, seed: int = 7, path: Path | str = "burnscar.png") -> tuple[Path, dict]:
    from cosmofire.synthetic import generate_burn_scar_scene

    scene = generate_burn_scar_scene(size=size, seed=seed)
    res = map_burn_scar(scene["nbr_pre"], scene["nbr_post"], float(scene["pixel_size_m"]))

    fig, axes = plt.subplots(1, 3, figsize=(12, 4.0))
    im0 = axes[0].imshow(res["dnbr"], cmap="RdYlGn_r", vmin=-0.3, vmax=0.8)
    axes[0].set_title("dNBR = NBR до − после")
    fig.colorbar(im0, ax=axes[0], fraction=0.046)
    cmap = matplotlib.colors.ListedColormap(["#0b0f14", "#4a7c4a", "#d6a83a", "#d6482d"])
    axes[1].imshow(res["severity"], cmap=cmap, vmin=0, vmax=3)
    axes[1].set_title("Классы тяжести гари")
    axes[2].imshow(scene["burn_mask"], cmap="Greys_r")
    axes[2].set_title("Эталонный контур")
    for ax in axes:
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
    a = res["area_ha"]
    fig.suptitle(
        f"Площадь гари: {a['burned_total']} га (низкая {a['low']}, средняя {a['moderate']}, высокая {a['high']}); "
        f"IoU {__import__('cosmofire.burnscar', fromlist=['iou']).iou(res['severity'] > 0, scene['burn_mask']):.3f}",
        fontsize=10,
    )
    fig.tight_layout()
    path = Path(path)
    fig.savefig(path)
    plt.close(fig)
    return path, res


def plot_quality(report: dict, path: Path | str = "quality.png") -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    p = report["filter"]
    axes[0].bar(["precision", "recall", "F1"], [p["precision"], p["recall"], p["f1"]], color="#4fc3ff")
    axes[0].set_ylim(0, 1.05)
    axes[0].set_title("Отсев ложных срабатываний (точки)")
    for i, v in enumerate([p["precision"], p["recall"], p["f1"]]):
        axes[0].text(i, v + 0.03, f"{v:.3f}", ha="center", fontsize=9)
    c = report["clusters"]
    vals = [c["site_precision"], c["site_recall"], c["site_f1"]]
    axes[1].bar(["precision", "recall", "F1"], vals, color="#ffb03a")
    axes[1].set_ylim(0, 1.05)
    axes[1].set_title(f"Очаги (ср. ошибка локализации {c['mean_loc_error_km']} км)")
    for i, v in enumerate(vals):
        axes[1].text(i, v + 0.03, f"{v:.3f}", ha="center", fontsize=9)
    fig.tight_layout()
    path = Path(path)
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_severity_legend(path: Path | str = "severity_legend.png") -> Path:
    fig, ax = plt.subplots(figsize=(6, 1.4))
    for i, label in enumerate(SEVERITY_LABELS):
        ax.barh(0, 1, left=i, color=["#0b0f14", "#4a7c4a", "#d6a83a", "#d6482d"][i], edgecolor="#333")
        ax.text(i + 0.5, 0, label, ha="center", va="center", color="w", fontsize=9)
    ax.set_xlim(0, 4)
    ax.set_yticks([])
    ax.grid(False)
    fig.tight_layout()
    path = Path(path)
    fig.savefig(path)
    plt.close(fig)
    return path
