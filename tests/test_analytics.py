"""Analytics package: cleaning, price model, forecast, zone score, exports (no database)."""

from decimal import Decimal
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from analytics import report
from analytics.cleaning import clean_dvf, clean_sales
from analytics.estimator import MLPriceEstimator
from analytics.predictive import PriceModel, forecast_sales, zone_scores
from app.models.enums import PropertyCategory, PropertyType
from app.services.pricing import PropertyFeatures

CITIES = [  # name, postal code, department, base price/m2, yearly growth
    ("Aix-en-Provence", "13100", "13", 5200, 0.04),
    ("Marseille", "13008", "13", 4300, 0.01),
    ("Lyon", "69003", "69", 5000, -0.02),
    ("Villeurbanne", "69100", "69", 3900, 0.05),
    ("Nantes", "44000", "44", 3800, 0.02),
]


def synthetic_sales(n: int = 600, seed: int = 0) -> pd.DataFrame:
    """Known ground truth: price/m2 = city base x growth^t x small-flat premium x noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        name, cp, dept, base, growth = CITIES[rng.integers(len(CITIES))]
        days = int(rng.integers(0, 3 * 365))
        surface = float(rng.uniform(20, 160))
        price_m2 = base * (1 + growth) ** (days / 365) * (1 + 15 / surface) * rng.normal(1, 0.05)
        rows.append(
            {
                "sale_date": pd.Timestamp("2023-11-01") + pd.Timedelta(days=days),
                "price": round(price_m2 * surface, -2),
                "surface_m2": surface,
                "rooms": max(1, int(surface // 25)),
                "property_type": "residential",
                "category": "apartment" if surface < 90 else "house",
                "city": name,
                "postal_code": cp,
                "department_code": dept,
                "latitude": None,
                "longitude": None,
                "days_to_sell": 60 if name != "Marseille" else 120,
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def sales():
    cleaned, _ = clean_sales(synthetic_sales())
    return cleaned


@pytest.fixture(scope="module")
def model(sales):
    # The ML tests need scikit-learn's compiled extensions (skipped on hosts that block them).
    pytest.importorskip("sklearn.ensemble")
    return PriceModel.train(sales)


# --- Cleaning ------------------------------------------------------------------------------
def test_cleaning_removes_bad_rows_and_logs_why():
    raw = synthetic_sales(200)
    dirty = pd.concat(
        [
            raw,
            raw.head(3),  # duplicates
            pd.DataFrame(
                [
                    {**raw.iloc[0], "price": None},  # missing price
                    {**raw.iloc[0], "surface_m2": 0},  # impossible surface
                    {**raw.iloc[0], "price": 9e9, "surface_m2": 30},
                ]
            ),  # outlier
        ],
        ignore_index=True,
    )
    cleaned, rep = clean_sales(dirty)
    removed = dict(rep.steps)
    assert removed["doublons exacts"] == 3
    assert removed["date, prix ou surface manquants"] == 1
    assert removed["prix ou surface non positifs"] == 1
    assert sum(n for rule, n in rep.steps if "aberrants" in rule) >= 1
    assert rep.final_rows == len(cleaned) and 9e9 not in cleaned["price"].to_numpy()
    assert {"price_m2", "month", "city_key", "log_surface"} <= set(cleaned.columns)
    assert "Lignes conservées" in rep.as_text()


def test_dvf_conversion_keeps_single_unit_sales():
    base = {
        "nature_mutation": "Vente",
        "valeur_fonciere": 250000,
        "surface_reelle_bati": 50,
        "nombre_pieces_principales": 2,
        "type_local": "Appartement",
        "nom_commune": "Lyon 3e Arrondissement",
        "code_postal": 69003,
        "code_departement": "69",
        "latitude": 45.76,
        "longitude": 4.85,
        "date_mutation": "2025-03-01",
    }
    raw = pd.DataFrame(
        [
            {**base, "id_mutation": "A"},
            {**base, "id_mutation": "B", "nature_mutation": "Echange"},
            {**base, "id_mutation": "C", "type_local": "Dépendance"},
            {**base, "id_mutation": "D"},
            {**base, "id_mutation": "D", "type_local": "Maison"},
            {
                **base,
                "id_mutation": "E",
                "type_local": "Maison",
                "valeur_fonciere": 400000,
                "surface_reelle_bati": 100,
                "code_postal": 1000,
            },
        ]
    )
    cleaned, rep = clean_dvf(raw)
    assert sorted(cleaned["category"]) == ["apartment", "house"]
    assert "01000" in set(cleaned["postal_code"])  # postal codes keep their leading zero
    assert rep.initial_rows == 6 and rep.final_rows == 2


# --- Price model ---------------------------------------------------------------------------
def test_price_model_beats_city_median_baseline(model):
    m = model.metrics
    assert m.mape < 0.10  # less than 10 % average error on unseen sales
    assert m.mape < m.baseline_mape
    assert m.r2 > 0.8


def test_price_model_learns_city_and_surface_effects(model):
    rows = pd.DataFrame(
        [
            {
                "sale_date": pd.Timestamp("2026-06-01"),
                "surface_m2": 60.0,
                "rooms": 2,
                "property_type": "residential",
                "category": "apartment",
                "city_key": f"{c} ({cp})",
                "department_code": d,
            }
            for c, cp, d in [("Aix-en-Provence", "13100", "13"), ("Nantes", "44000", "44")]
        ]
    )
    aix, nantes = model.predict(rows)
    assert aix > nantes * 1.2


def test_model_persistence_round_trip(model, tmp_path):
    path = model.save(tmp_path / "m.joblib")
    loaded = PriceModel.load(path)
    assert loaded.metrics == model.metrics
    assert PriceModel.load(tmp_path / "missing.joblib") is None


def test_training_needs_enough_data(sales):
    pytest.importorskip("sklearn.ensemble")
    with pytest.raises(ValueError):
        PriceModel.train(sales.head(10))


def test_ml_estimator_and_fallback(model):
    city = SimpleNamespace(name="Lyon", postal_code="69003", department_code="69")
    features = PropertyFeatures(PropertyType.RESIDENTIAL, PropertyCategory.APARTMENT, 50, 2, city)
    fallback = SimpleNamespace(estimate=lambda f: Decimal("1"))
    price = MLPriceEstimator(fallback, model=model).estimate(features)
    assert price % 1000 == 0 and 150_000 < price < 400_000
    no_model = MLPriceEstimator(fallback)
    no_model.model = None
    assert no_model.estimate(features) == Decimal("1")
    # A home without room count goes to the market average instead of the model.
    apartment = (PropertyType.RESIDENTIAL, PropertyCategory.APARTMENT)
    unknown_rooms = PropertyFeatures(*apartment, 50, 0, city)
    assert MLPriceEstimator(fallback, model=model).estimate(unknown_rooms) == Decimal("1")


# --- Forecast ------------------------------------------------------------------------------
def monthly_series(months: int = 36, trend: float = 1.0) -> pd.DataFrame:
    dates = pd.date_range("2023-11-01", periods=months, freq="MS")
    season = 10 * np.sin(2 * np.pi * dates.month / 12)
    return pd.DataFrame(
        {
            "month": dates,
            "sales_count": 50 + trend * np.arange(months) + season,
            "avg_price_m2": 4000 * 1.03 ** (np.arange(months) / 12),
        }
    )


def test_forecast_projects_trend_and_excludes_current_month():
    fc = forecast_sales(monthly_series(), horizon=12, today=pd.Timestamp("2026-10-15"))
    assert fc.history["month"].max() == pd.Timestamp("2026-09-01")  # October is incomplete
    assert fc.forecast["month"].iloc[0] == pd.Timestamp("2026-10-01")
    assert len(fc.forecast) == 12
    assert fc.price_trend_yearly == pytest.approx(0.03, abs=0.002)
    assert fc.total_sales(12) > fc.total_sales(6) > 0
    assert (fc.forecast["sales_low"] <= fc.forecast["sales_count"]).all()


def test_forecast_needs_a_year_of_history():
    with pytest.raises(ValueError):
        forecast_sales(monthly_series(8), today=pd.Timestamp("2024-08-15"))


# --- Zone score ----------------------------------------------------------------------------
def test_zone_score_ranks_growing_affordable_cities_first(sales):
    zones = zone_scores(sales)
    assert zones["score"].between(0, 100).all()
    assert zones["score"].is_monotonic_decreasing
    # Villeurbanne: +5 %/year and cheaper than Lyon -> best; Lyon: falling prices -> last.
    assert zones.iloc[0]["city_key"] == "Villeurbanne (69100)"
    assert zones.iloc[-1]["city_key"] == "Lyon (69003)"


# --- Exports -------------------------------------------------------------------------------
def test_csv_export_is_excel_friendly(sales):
    data = report.sales_csv(sales.head(5))
    assert data.startswith("﻿".encode())  # BOM so Excel detects UTF-8
    header = data.decode("utf-8-sig").splitlines()[0]
    assert header.startswith("date_vente;") and "prix_m2" in header


def test_pdf_export_is_a_valid_pdf(sales):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ax.plot([1, 2], [1, 2])
    content = report.ReportContent(
        title="Test",
        kpis={"Ventes": "10"},
        figures=[fig],
        city_table=pd.DataFrame({"Ville": ["Aix"], "Ventes": [3]}),
    )
    pdf = report.sales_pdf(content)
    assert pdf.startswith(b"%PDF") and len(pdf) > 2000


def test_signed_percent_uses_french_typography():
    from app.core.formatting import signed_percent

    assert signed_percent(0.0142) == "+1,4 %"
    assert signed_percent(-0.04) == "−4,0 %"
    assert signed_percent(None) == "—"
