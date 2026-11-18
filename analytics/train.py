"""Command line: clean the data and train the price model.

    python -m analytics.train                 # from the platform's sales (database)
    python -m analytics.train --dvf dvf.csv   # from a geo-dvf extract (data.gouv.fr)
    python -m analytics.train --if-missing    # used at container start-up
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from analytics.cleaning import clean_dvf, clean_sales
from analytics.predictive import PriceModel
from app.core.config import get_settings


def load_sales(dvf: Path | None):
    if dvf:
        raw = pd.read_csv(dvf, low_memory=False)
        return clean_dvf(raw)
    from app.core.database import SessionLocal
    from app.repositories.analytics_repository import AnalyticsRepository

    with SessionLocal() as db:
        return clean_sales(AnalyticsRepository(db).sales_dataset())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Entraîne le modèle d'estimation de prix.")
    parser.add_argument("--dvf", type=Path, help="fichier CSV geo-dvf à utiliser")
    parser.add_argument(
        "--if-missing", action="store_true", help="ne rien faire si un modèle existe déjà"
    )
    args = parser.parse_args(argv)

    target = Path(get_settings().analytics_model_path)
    if args.if_missing and target.exists():
        print(f"Modèle déjà présent : {target}")
        return 0
    sales, report = load_sales(args.dvf)
    print(report.as_text())
    if len(sales) < 50:
        print("Pas assez de ventes pour entraîner un modèle.")
        return 0 if args.if_missing else 1
    model = PriceModel.train(sales)
    model.save(target)
    m = model.metrics
    print(f"Modèle enregistré : {target}")
    print(f"Erreur moyenne (MAPE) : {m.mape:.1%} | MAE : {m.mae_eur:,.0f} EUR | R2 : {m.r2:.3f}")
    print(f"Référence 'médiane ville et catégorie x surface' : {m.baseline_mape:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
