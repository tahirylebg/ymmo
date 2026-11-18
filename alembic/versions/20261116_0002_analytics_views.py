"""Hand-written analytical SQL views (joins, aggregates, window functions).

These views are the SQL layer of the analytics module: the API and the dashboard read
them through AnalyticsRepository with plain SELECTs, so heavy aggregation runs inside
PostgreSQL (close to the data, using the indexes) instead of in Python.

Revision ID: 0002_analytics_views
Revises: 619911125435
Create Date: 2026-11-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_analytics_views"
down_revision: str | None = "619911125435"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Order matters for creation (no dependency between them today, but keep it explicit).
VIEWS: dict[str, str] = {
    # Average / median price per m2 by city: listings vs. actual sales.
    "v_city_market_stats": """
        WITH listings AS (
            SELECT city_id,
                   COUNT(*) FILTER (WHERE status <> 'sold')            AS active_listings,
                   AVG(price / surface_m2) FILTER (WHERE status <> 'sold') AS avg_listing_price_m2
            FROM properties
            GROUP BY city_id
        ),
        sales AS (
            SELECT p.city_id,
                   COUNT(*)                                       AS sales_count,
                   AVG(t.final_price / p.surface_m2)              AS avg_sale_price_m2,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (
                       ORDER BY (t.final_price / p.surface_m2)::float8
                   )                                              AS median_sale_price_m2
            FROM transactions t
            JOIN properties p ON p.id = t.property_id
            GROUP BY p.city_id
        )
        SELECT c.id                                        AS city_id,
               c.name                                      AS city,
               c.postal_code,
               c.department_code,
               COALESCE(l.active_listings, 0)              AS active_listings,
               ROUND(l.avg_listing_price_m2::numeric, 2)   AS avg_listing_price_m2,
               COALESCE(s.sales_count, 0)                  AS sales_count,
               ROUND(s.avg_sale_price_m2::numeric, 2)      AS avg_sale_price_m2,
               ROUND(s.median_sale_price_m2::numeric, 2)   AS median_sale_price_m2
        FROM cities c
        LEFT JOIN listings l ON l.city_id = c.id
        LEFT JOIN sales s    ON s.city_id = c.id
    """,
    # Time to sell and negotiation margin for each concluded sale.
    "v_sale_durations": """
        SELECT t.id                                       AS transaction_id,
               p.id                                       AS property_id,
               p.agency_id,
               p.city_id,
               p.property_type,
               p.category,
               p.published_at::date                       AS listed_on,
               t.signed_at                                AS sold_on,
               (t.signed_at - p.published_at::date)       AS days_to_sell,
               p.price                                    AS asking_price,
               t.final_price,
               ROUND((1 - t.final_price / p.price) * 100, 2) AS negotiation_pct
        FROM transactions t
        JOIN properties p ON p.id = t.property_id
    """,
    # Monthly sales with a 3-month moving average and year-to-date revenue (windows).
    "v_monthly_sales": """
        SELECT date_trunc('month', t.signed_at)::date             AS month,
               COUNT(*)                                           AS sales_count,
               SUM(t.final_price)                                 AS revenue,
               ROUND(AVG(t.final_price / p.surface_m2)::numeric, 2) AS avg_price_m2,
               ROUND(AVG(COUNT(*)) OVER (
                   ORDER BY date_trunc('month', t.signed_at)
                   ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
               ), 2)                                              AS sales_moving_avg_3m,
               SUM(SUM(t.final_price)) OVER (
                   PARTITION BY date_part('year', t.signed_at)
                   ORDER BY date_trunc('month', t.signed_at)
               )                                                  AS revenue_ytd
        FROM transactions t
        JOIN properties p ON p.id = t.property_id
        GROUP BY date_trunc('month', t.signed_at), date_part('year', t.signed_at)
    """,
    # Popularity score (views, favorites, visits, offers) with global and per-city ranks.
    "v_property_popularity": """
        WITH v AS (
            SELECT property_id,
                   COUNT(*) AS views_count,
                   COUNT(*) FILTER (WHERE viewed_at >= now() - INTERVAL '30 days') AS views_30d
            FROM property_views GROUP BY property_id
        ),
        f AS (SELECT property_id, COUNT(*) AS favorites_count FROM favorites GROUP BY property_id),
        vi AS (
            SELECT property_id, COUNT(*) AS visits_count
            FROM visits WHERE status <> 'cancelled' GROUP BY property_id
        ),
        o AS (SELECT property_id, COUNT(*) AS offers_count FROM offers GROUP BY property_id),
        scored AS (
            SELECT p.id AS property_id, p.reference, p.title, p.city_id, p.agency_id,
                   p.status, p.price,
                   COALESCE(v.views_count, 0)      AS views_count,
                   COALESCE(v.views_30d, 0)        AS views_30d,
                   COALESCE(f.favorites_count, 0)  AS favorites_count,
                   COALESCE(vi.visits_count, 0)    AS visits_count,
                   COALESCE(o.offers_count, 0)     AS offers_count,
                   COALESCE(v.views_count, 0)
                     + 3 * COALESCE(f.favorites_count, 0)
                     + 5 * COALESCE(vi.visits_count, 0)
                     + 8 * COALESCE(o.offers_count, 0) AS popularity_score
            FROM properties p
            LEFT JOIN v  ON v.property_id  = p.id
            LEFT JOIN f  ON f.property_id  = p.id
            LEFT JOIN vi ON vi.property_id = p.id
            LEFT JOIN o  ON o.property_id  = p.id
        )
        SELECT s.*,
               DENSE_RANK() OVER (ORDER BY s.popularity_score DESC)                       AS global_rank,
               DENSE_RANK() OVER (PARTITION BY s.city_id ORDER BY s.popularity_score DESC) AS city_rank
        FROM scored s
    """,
    # Agency leaderboard: sales, revenue, average time to sell, rank by revenue.
    "v_agency_performance": """
        SELECT a.id                                              AS agency_id,
               a.code,
               a.name,
               COUNT(t.id)                                       AS sales_count,
               COALESCE(SUM(t.final_price), 0)                   AS revenue,
               ROUND(AVG(t.signed_at - p.published_at::date), 1) AS avg_days_to_sell,
               RANK() OVER (ORDER BY COALESCE(SUM(t.final_price), 0) DESC) AS revenue_rank
        FROM agencies a
        LEFT JOIN properties p   ON p.agency_id = a.id
        LEFT JOIN transactions t ON t.property_id = p.id
        GROUP BY a.id, a.code, a.name
    """,
}


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return  # views use PostgreSQL syntax (FILTER, PERCENTILE_CONT, date_trunc)
    for name, sql in VIEWS.items():
        op.execute(f"CREATE OR REPLACE VIEW {name} AS {sql}")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for name in reversed(VIEWS):
        op.execute(f"DROP VIEW IF EXISTS {name}")
