"""Hand-written SQL for analytics (PostgreSQL).

Aggregations run in the database, on top of the views created by the migration
`0002_analytics_views`. Every query is parameterised (no string formatting of user input).
"""

from decimal import Decimal

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

# Sales dataset for the machine-learning model and the exports (one row per sale).
SALES_DATASET_SQL = text(
    """
    SELECT t.signed_at                              AS sale_date,
           t.final_price                            AS price,
           p.surface_m2,
           p.rooms,
           p.property_type,
           p.category,
           c.name                                   AS city,
           c.postal_code,
           c.department_code,
           p.latitude,
           p.longitude,
           a.code                                   AS agency_code,
           p.reference,
           p.price                                  AS asking_price,
           (t.signed_at - p.published_at::date)     AS days_to_sell
    FROM transactions t
    JOIN properties p ON p.id = t.property_id
    JOIN cities c     ON c.id = p.city_id
    JOIN agencies a   ON a.id = p.agency_id
    WHERE (CAST(:agency_id AS integer) IS NULL OR p.agency_id = :agency_id)
      AND (CAST(:year AS integer) IS NULL OR EXTRACT(YEAR FROM t.signed_at) = :year)
    ORDER BY t.signed_at
"""
)

# Time to sell per category: average, median and 90th percentile.
SALE_DURATION_SQL = text(
    """
    SELECT category,
           COUNT(*)                                                   AS sales,
           ROUND(AVG(days_to_sell), 1)                                AS avg_days,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY days_to_sell)  AS median_days,
           PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY days_to_sell)  AS p90_days,
           ROUND(AVG(negotiation_pct), 2)                             AS avg_negotiation_pct
    FROM v_sale_durations
    GROUP BY category
    ORDER BY median_days
"""
)

# Most popular listings still on sale (view built with DENSE_RANK window functions).
POPULAR_SQL = text(
    """
    SELECT pp.property_id, pp.reference, pp.title, pp.price, pp.status,
           c.name AS city, pp.views_count, pp.views_30d, pp.favorites_count,
           pp.visits_count, pp.offers_count, pp.popularity_score, pp.global_rank, pp.city_rank
    FROM v_property_popularity pp
    JOIN cities c ON c.id = pp.city_id
    WHERE pp.status <> 'sold'
    ORDER BY pp.global_rank, pp.property_id
    LIMIT :limit
"""
)

# Demand per city: recent views per active listing (input of the zone score).
DEMAND_SQL = text(
    """
    SELECT c.name || ' (' || c.postal_code || ')'  AS city_key,
           COUNT(*)                                AS active_listings,
           ROUND(AVG(pp.views_30d), 2)             AS views_per_listing
    FROM v_property_popularity pp
    JOIN cities c ON c.id = pp.city_id
    WHERE pp.status <> 'sold'
    GROUP BY c.name, c.postal_code
"""
)


class AnalyticsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _frame(self, query, **params) -> pd.DataFrame:
        result = self.db.execute(query, params)
        frame = pd.DataFrame(result.mappings().all(), columns=list(result.keys()))
        # NUMERIC columns arrive as Decimal objects: convert them once for numpy/pandas.
        for column in frame.select_dtypes(include="object").columns:
            sample = frame[column].dropna()
            if not sample.empty and isinstance(sample.iloc[0], Decimal):
                frame[column] = frame[column].astype(float)
        return frame

    def sales_dataset(self, agency_id: int | None = None, year: int | None = None):
        return self._frame(SALES_DATASET_SQL, agency_id=agency_id, year=year)

    def city_market_stats(self) -> pd.DataFrame:
        return self._frame(
            text(
                "SELECT * FROM v_city_market_stats WHERE sales_count > 0 "
                "ORDER BY avg_sale_price_m2 DESC"
            )
        )

    def monthly_sales(self) -> pd.DataFrame:
        return self._frame(text("SELECT * FROM v_monthly_sales ORDER BY month"))

    def agency_performance(self) -> pd.DataFrame:
        return self._frame(text("SELECT * FROM v_agency_performance ORDER BY revenue_rank"))

    def sale_durations(self) -> pd.DataFrame:
        return self._frame(SALE_DURATION_SQL)

    def popular_properties(self, limit: int = 10) -> pd.DataFrame:
        return self._frame(POPULAR_SQL, limit=limit)

    def demand_by_city(self) -> pd.DataFrame:
        return self._frame(DEMAND_SQL)
