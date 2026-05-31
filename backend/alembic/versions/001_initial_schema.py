"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "restaurants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("yelp_id", sa.String(), unique=True, nullable=True),
        sa.Column("google_place_id", sa.String(), unique=True, nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("address", sa.String()),
        sa.Column("lat", sa.Float()),
        sa.Column("lng", sa.Float()),
        sa.Column("cuisine_tags", ARRAY(sa.String())),
        sa.Column("price_level", sa.String()),
        sa.Column("photo_url", sa.String()),
    )
    op.create_index("ix_restaurants_yelp_id", "restaurants", ["yelp_id"])
    op.create_index("ix_restaurants_google_place_id", "restaurants", ["google_place_id"])

    op.create_table(
        "menu_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "restaurant_id",
            sa.Integer(),
            sa.ForeignKey("restaurants.id"),
            index=True,
        ),
        sa.Column("item_name", sa.String(), nullable=False),
        sa.Column("price", sa.Numeric(5, 2)),
        sa.Column("photo_url", sa.String()),
        sa.Column("source", sa.String()),
    )

    op.create_table(
        "search_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cache_key", sa.String(), unique=True),
        sa.Column("query_address", sa.String(), nullable=False),
        sa.Column("normalized_address", sa.String()),
        sa.Column("travel_mode", sa.String(), nullable=False),
        sa.Column("lat", sa.Float()),
        sa.Column("lng", sa.Float()),
        sa.Column("results_json", JSONB(), nullable=False),
        sa.Column("result_count", sa.Integer()),
        sa.Column("radius_expanded", sa.Boolean(), default=False),
        sa.Column(
            "cached_at", sa.DateTime(), server_default=sa.text("NOW()")
        ),
        sa.Column("expires_at", sa.DateTime()),
    )
    op.create_index("ix_search_cache_cache_key", "search_cache", ["cache_key"])

    op.create_table(
        "review_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "restaurant_id",
            sa.Integer(),
            sa.ForeignKey("restaurants.id"),
            index=True,
        ),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("rating", sa.Numeric(2, 1)),
        sa.Column("review_count", sa.Integer()),
        sa.Column("snippets", ARRAY(sa.String())),
        sa.Column("dish_mentions", ARRAY(sa.String())),
        sa.Column("raw_reviews", JSONB()),
        sa.Column(
            "cached_at", sa.DateTime(), server_default=sa.text("NOW()")
        ),
        sa.Column("expires_at", sa.DateTime()),
    )
    op.create_index(
        "ix_review_cache_expires", "review_cache", ["expires_at"]
    )


def downgrade():
    op.drop_table("review_cache")
    op.drop_table("search_cache")
    op.drop_table("menu_items")
    op.drop_table("restaurants")
