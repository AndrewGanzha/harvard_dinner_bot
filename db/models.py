from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    goal: Mapped[str | None] = mapped_column(String(32), nullable=True)
    allergies: Mapped[list[str]] = mapped_column(JSON, default=list)
    excluded_products: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_cuisine: Mapped[str | None] = mapped_column(String(64), nullable=True)
    preferred_complexity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    recipes: Mapped[list["Recipe"]] = relationship(back_populates="user")
    votes: Mapped[list["RecipeVote"]] = relationship(back_populates="user")
    favorites: Mapped[list["UserFavorite"]] = relationship(back_populates="user")


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_type: Mapped[str] = mapped_column(String(32), default="ingredients")
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    servings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_ingredients: Mapped[list[str]] = mapped_column(JSON, default=list)
    supplemented_ingredients: Mapped[list[str]] = mapped_column(JSON, default=list)
    plate_map: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    llm_response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="recipes")
    votes: Mapped[list["RecipeVote"]] = relationship(back_populates="recipe")
    favorites: Mapped[list["UserFavorite"]] = relationship(back_populates="recipe")


class RecipeVote(Base):
    __tablename__ = "recipe_votes"
    __table_args__ = (
        UniqueConstraint("user_id", "recipe_id", name="uq_recipe_votes_user_recipe"),
        CheckConstraint("vote in (-1, 1)", name="ck_recipe_votes_vote_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), index=True)
    vote: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="votes")
    recipe: Mapped["Recipe"] = relationship(back_populates="votes")


class UserFavorite(Base):
    __tablename__ = "user_favorites"
    __table_args__ = (UniqueConstraint("user_id", "recipe_id", name="uq_user_favorites_user_recipe"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="favorites")
    recipe: Mapped["Recipe"] = relationship(back_populates="favorites")
