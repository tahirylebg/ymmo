"""Data cleaning and preparation.

Two sources share the same output schema (`SALES_COLUMNS`) so every downstream analysis
works on either of them:

* the platform's own sales (SQL query on transactions / properties / cities);
* the French open data "DVF" (Demandes de valeurs foncières, geo-dvf CSV format).

Each rule is applied in order and logged in a `CleaningReport`, so the report can say
exactly how many rows were removed and why (traceability for the jury / the client).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

SALES_COLUMNS = [
    "sale_date",
    "price",
    "surface_m2",
    "rooms",
    "property_type",
    "category",
    "city",
    "postal_code",
    "department_code",
    "latitude",
    "longitude",
]

# DVF "type_local" -> our (property_type, category)
DVF_TYPES = {
    "Appartement": ("residential", "apartment"),
    "Maison": ("residential", "house"),
    "Local industriel. commercial ou assimilé": ("professional", "retail"),
}


@dataclass
class CleaningReport:
    initial_rows: int = 0
    steps: list[tuple[str, int]] = field(default_factory=list)

    def log(self, rule: str, before: int, after: int) -> None:
        self.steps.append((rule, before - after))

    @property
    def final_rows(self) -> int:
        return self.initial_rows - sum(removed for _, removed in self.steps)

    def as_text(self) -> str:
        lines = [f"Lignes en entrée : {self.initial_rows}"]
        lines += [f"  - {rule} : {removed} ligne(s) supprimée(s)" for rule, removed in self.steps]
        lines.append(f"Lignes conservées : {self.final_rows}")
        return "\n".join(lines)


def _apply(df: pd.DataFrame, report: CleaningReport, rule: str, mask: pd.Series) -> pd.DataFrame:
    before = len(df)
    df = df[mask]
    report.log(rule, before, len(df))
    return df


def clean_sales(raw: pd.DataFrame, iqr_factor: float = 3.0) -> tuple[pd.DataFrame, CleaningReport]:
    """Normalise types, remove unusable rows and extreme outliers, add derived features."""
    report = CleaningReport(initial_rows=len(raw))
    df = raw.copy()

    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
    for column in ("price", "surface_m2", "rooms", "latitude", "longitude"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    for column in ("property_type", "category", "city", "postal_code", "department_code"):
        df[column] = df[column].astype("string").str.strip()

    df = _apply(df, report, "doublons exacts", ~df.duplicated())
    df = _apply(
        df,
        report,
        "date, prix ou surface manquants",
        df[["sale_date", "price", "surface_m2"]].notna().all(axis=1),
    )
    df = _apply(
        df, report, "prix ou surface non positifs", (df["price"] > 0) & (df["surface_m2"] > 0)
    )
    df["rooms"] = df["rooms"].fillna(0).clip(lower=0)

    df["price_m2"] = df["price"] / df["surface_m2"]
    # Outliers: price per m2 outside [Q1 - k*IQR, Q3 + k*IQR] within each category
    # (a 3,000 m2 warehouse and a studio must not share the same bounds).
    grouped = df.groupby("category")["price_m2"]
    q1, q3 = grouped.transform("quantile", 0.25), grouped.transform("quantile", 0.75)
    iqr = q3 - q1
    df = _apply(
        df,
        report,
        f"prix au m² aberrants (IQR x{iqr_factor:g} par catégorie)",
        df["price_m2"].between(q1 - iqr_factor * iqr, q3 + iqr_factor * iqr),
    )

    df = add_features(df)
    return df.reset_index(drop=True), report


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derived columns used by statistics and models."""
    df = df.copy()
    df["price_m2"] = df["price"] / df["surface_m2"]
    df["month"] = df["sale_date"].dt.to_period("M").dt.to_timestamp()
    df["year"] = df["sale_date"].dt.year
    df["city_key"] = df["city"] + " (" + df["postal_code"] + ")"
    df["log_surface"] = np.log(df["surface_m2"])
    return df


def clean_dvf(raw: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """Convert a geo-dvf extract (data.gouv.fr) into the common sales schema.

    DVF lists one row per *lot* of a transaction: a sale of a flat with a cellar produces
    two rows sharing the same `id_mutation`. We keep sales ("Vente") of a single
    residential/commercial unit, then reuse `clean_sales`.
    """
    report = CleaningReport(initial_rows=len(raw))
    df = raw.copy()
    df = _apply(df, report, "mutations autres que des ventes", df["nature_mutation"] == "Vente")
    df = _apply(
        df,
        report,
        "types de locaux non gérés (dépendances, sans local)",
        df["type_local"].isin(DVF_TYPES),
    )
    lots = df.groupby("id_mutation")["type_local"].transform("size")
    df = _apply(df, report, "ventes multi-lots (prix non attribuable à un seul bien)", lots == 1)

    mapped = df["type_local"].map(DVF_TYPES)
    converted = pd.DataFrame(
        {
            "sale_date": df["date_mutation"],
            "price": df["valeur_fonciere"],
            "surface_m2": df["surface_reelle_bati"],
            "rooms": df["nombre_pieces_principales"],
            "property_type": mapped.str[0],
            "category": mapped.str[1],
            "city": df["nom_commune"],
            "postal_code": df["code_postal"].astype("string").str.zfill(5),
            "department_code": df["code_departement"].astype("string"),
            "latitude": df["latitude"],
            "longitude": df["longitude"],
        }
    )
    cleaned, sales_report = clean_sales(converted)
    report.steps += sales_report.steps
    return cleaned, report
