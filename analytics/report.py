"""Sales report exports: CSV (raw data) and PDF (KPIs + charts + tables)."""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

from analytics import charts

CSV_COLUMNS = {
    "sale_date": "date_vente",
    "reference": "reference",
    "agency_code": "agence",
    "city": "ville",
    "postal_code": "code_postal",
    "property_type": "usage",
    "category": "type_bien",
    "surface_m2": "surface_m2",
    "rooms": "pieces",
    "asking_price": "prix_affiche",
    "price": "prix_vente",
    "price_m2": "prix_m2",
    "days_to_sell": "delai_vente_jours",
}


def sales_csv(sales: pd.DataFrame, labels: dict[str, str] | None = None) -> bytes:
    """French-friendly CSV (semicolon separator, comma decimals, UTF-8 BOM for Excel)."""
    data = sales.copy()
    if labels:
        for column in ("property_type", "category"):
            data[column] = data[column].map(lambda v: labels.get(v, v))
    data["price_m2"] = (data["price"].astype(float) / data["surface_m2"].astype(float)).round(2)
    data = data[[c for c in CSV_COLUMNS if c in data]].rename(columns=CSV_COLUMNS)
    return data.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig")


@dataclass
class ReportContent:
    title: str
    kpis: dict[str, str]
    figures: list  # matplotlib figures
    city_table: pd.DataFrame


def _text_page(pdf: PdfPages, content: ReportContent) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))  # A4 portrait
    fig.text(0.08, 0.92, "Ymmo", fontsize=28, fontweight="bold", color=charts.PRIMARY)
    fig.text(0.08, 0.88, content.title, fontsize=16, color=charts.INK)
    fig.text(0.08, 0.855, f"Édité le {date.today():%d/%m/%Y}", fontsize=10, color=charts.MUTED)
    y = 0.79
    for label, value in content.kpis.items():
        fig.text(0.08, y, label, fontsize=11, color=charts.MUTED)
        fig.text(0.62, y, value, fontsize=12, fontweight="bold", color=charts.INK)
        y -= 0.04
    fig.text(
        0.08,
        0.08,
        "Données : ventes conclues sur la plateforme Ymmo. Prévisions "
        "indicatives (régression tendance + saisonnalité).",
        fontsize=8,
        color=charts.MUTED,
    )
    pdf.savefig(fig)
    plt.close(fig)


def _table_page(pdf: PdfPages, table: pd.DataFrame, title: str) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.text(0.08, 0.94, title, fontsize=14, fontweight="bold", color=charts.INK)
    ax = fig.add_axes((0.06, 0.05, 0.88, 0.86))
    ax.axis("off")
    rendered = ax.table(
        cellText=table.values,
        colLabels=list(table.columns),
        loc="upper center",
        cellLoc="right",
        colLoc="right",
    )
    rendered.auto_set_font_size(False)
    rendered.set_fontsize(8)
    rendered.scale(1, 1.3)
    pdf.savefig(fig)
    plt.close(fig)


def sales_pdf(content: ReportContent) -> bytes:
    buffer = io.BytesIO()
    with PdfPages(buffer, metadata={"Title": content.title, "Author": "Ymmo"}) as pdf:
        _text_page(pdf, content)
        for fig in content.figures:
            pdf.savefig(fig)
            plt.close(fig)
        _table_page(pdf, content.city_table, "Marché par ville")
    return buffer.getvalue()
