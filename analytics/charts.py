"""Charts (matplotlib) rendered as SVG for the dashboard and reused in the PDF report.

Server-side SVG keeps the page light (no 3 MB charting library) and works without
JavaScript. Every chart is paired with a data table in the page for screen readers.
"""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")  # no display server in the container

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

# Same palette as app/static/css/main.css (ink primary series, brass secondary series, warm greys)
PRIMARY = "#1a1814"
ACCENT = "#a38253"
MUTED = "#8c8273"
GRID = "#d6ccbb"
INK = "#2e2a25"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "figure.facecolor": "none",  # the page provides the background
        "axes.facecolor": "none",
        "font.size": 10,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK,
        "axes.titleweight": "bold",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": INK,
        "ytick.color": INK,
        "svg.fonttype": "none",  # keep real text in the SVG (selectable, lighter)
    }
)

_thousands = FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " "))


def _figure(height: float = 4.2) -> tuple[Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=(8, height), layout="constrained")
    ax.grid(axis="both", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    return fig, ax


def to_svg(fig: Figure) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="svg", metadata={"Date": None})
    plt.close(fig)
    return buffer.getvalue()


def price_by_city(stats: pd.DataFrame, top: int = 15) -> Figure:
    data = stats.nlargest(top, "avg_sale_price_m2").iloc[::-1]
    fig, ax = _figure(height=0.32 * len(data) + 1.2)
    labels = data["city"] + " (" + data["postal_code"] + ")"
    ax.barh(labels, data["avg_sale_price_m2"].astype(float), color=PRIMARY)
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(_thousands)
    ax.set_xlabel("Prix moyen de vente (€/m²)")
    ax.set_title("Prix moyen au m² par ville", loc="left")
    return fig


def sales_forecast(history: pd.DataFrame, forecast: pd.DataFrame) -> Figure:
    fig, ax = _figure()
    ax.plot(
        history["month"],
        history["sales_count"],
        color=PRIMARY,
        linewidth=2,
        label="Ventes mensuelles (historique)",
    )
    ax.plot(
        forecast["month"],
        forecast["sales_count"],
        color=ACCENT,
        linewidth=2,
        linestyle="--",
        label="Prévision",
    )
    ax.fill_between(
        forecast["month"],
        forecast["sales_low"],
        forecast["sales_high"],
        color=ACCENT,
        alpha=0.15,
        label="Intervalle à 95 %",
    )
    ax.set_ylabel("Nombre de ventes")
    ax.set_ylim(bottom=0)
    ax.set_title("Ventes mensuelles et prévision à 12 mois", loc="left")
    ax.legend(frameon=False, loc="upper left")
    return fig


def price_trend(history: pd.DataFrame, forecast: pd.DataFrame) -> Figure:
    fig, ax = _figure()
    ax.plot(
        history["month"],
        history["avg_price_m2"].astype(float),
        color=PRIMARY,
        linewidth=2,
        label="Prix moyen au m² (ventes)",
    )
    ax.plot(
        forecast["month"],
        forecast["avg_price_m2"],
        color=ACCENT,
        linestyle="--",
        linewidth=2,
        label="Tendance projetée",
    )
    ax.yaxis.set_major_formatter(_thousands)
    ax.set_ylabel("€/m²")
    ax.set_title("Évolution du prix moyen au m²", loc="left")
    ax.legend(frameon=False, loc="upper left")
    return fig


def zone_scores(zones: pd.DataFrame, top: int = 10) -> Figure:
    data = zones.head(top).iloc[::-1]
    fig, ax = _figure(height=0.36 * len(data) + 1.2)
    ax.barh(data["city_key"], data["score"], color=ACCENT)
    ax.set_xlim(0, 100)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Score d'opportunité (0 à 100)")
    ax.set_title("Zones intéressantes où acheter", loc="left")
    return fig


def sale_durations(durations: pd.DataFrame, labels: dict[str, str]) -> Figure:
    data = durations.sort_values("median_days")
    fig, ax = _figure(height=3.4)
    names = data["category"].map(lambda c: labels.get(c, c))
    ax.bar(names, data["median_days"].astype(float), color=PRIMARY, label="Médiane")
    ax.scatter(
        names,
        data["p90_days"].astype(float),
        color=ACCENT,
        zorder=3,
        label="9 ventes sur 10 en moins de",
    )
    ax.set_ylabel("Jours entre mise en vente et signature")
    ax.set_title("Délai de vente par type de bien", loc="left")
    ax.legend(frameon=False)
    ax.grid(axis="x", visible=False)
    return fig


def agency_revenue(agencies: pd.DataFrame) -> Figure:
    data = agencies.sort_values("revenue")
    fig, ax = _figure(height=0.32 * len(data) + 1.2)
    ax.barh(data["code"], data["revenue"].astype(float) / 1e6, color=PRIMARY)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Volume de ventes cumulé (M€)")
    ax.set_title("Performance des agences", loc="left")
    return fig
