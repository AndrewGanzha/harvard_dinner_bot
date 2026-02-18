"""Initial schema.

Revision ID: 20260218_0001
Revises:
Create Date: 2026-02-18 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260218_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("goal", sa.String(length=32), nullable=True),
        sa.Column("allergies", sa.JSON(), nullable=False),
        sa.Column("excluded_products", sa.JSON(), nullable=False),
        sa.Column("preferred_cuisine", sa.String(length=64), nullable=True),
        sa.Column("preferred_complexity", sa.String(length=32), nullable=True),
        sa.Column("time_limit_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tg_user_id", name="uq_users_tg_user_id"),
    )
    op.create_index("ix_users_tg_user_id", "users", ["tg_user_id"], unique=True)

    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("time_minutes", sa.Integer(), nullable=True),
        sa.Column("servings", sa.Integer(), nullable=True),
        sa.Column("source_ingredients", sa.JSON(), nullable=False),
        sa.Column("supplemented_ingredients", sa.JSON(), nullable=False),
        sa.Column("plate_map", sa.JSON(), nullable=False),
        sa.Column("llm_response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_recipes_user_id", "recipes", ["user_id"], unique=False)

    op.create_table(
        "recipe_votes",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("vote", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("vote in (-1, 1)", name="ck_recipe_votes_vote_value"),
        sa.UniqueConstraint("user_id", "recipe_id", name="uq_recipe_votes_user_recipe"),
    )
    op.create_index("ix_recipe_votes_user_id", "recipe_votes", ["user_id"], unique=False)
    op.create_index("ix_recipe_votes_recipe_id", "recipe_votes", ["recipe_id"], unique=False)

    op.create_table(
        "user_favorites",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "recipe_id", name="uq_user_favorites_user_recipe"),
    )
    op.create_index("ix_user_favorites_user_id", "user_favorites", ["user_id"], unique=False)
    op.create_index("ix_user_favorites_recipe_id", "user_favorites", ["recipe_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_favorites_recipe_id", table_name="user_favorites")
    op.drop_index("ix_user_favorites_user_id", table_name="user_favorites")
    op.drop_table("user_favorites")

    op.drop_index("ix_recipe_votes_recipe_id", table_name="recipe_votes")
    op.drop_index("ix_recipe_votes_user_id", table_name="recipe_votes")
    op.drop_table("recipe_votes")

    op.drop_index("ix_recipes_user_id", table_name="recipes")
    op.drop_table("recipes")

    op.drop_index("ix_users_tg_user_id", table_name="users")
    op.drop_table("users")
