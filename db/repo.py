from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Recipe, RecipeVote, User, UserFavorite

RequestType = Literal["ingredients", "random"]
BrowseScope = Literal["top", "favorites", "history"]
GoalType = Literal["lose", "maintain", "gain"]


@dataclass(slots=True)
class RecipeWithRating:
    recipe: Recipe
    rating: int


@dataclass(slots=True)
class UserSettings:
    goal: GoalType | None = None
    allergies: list[str] | None = None
    excluded_products: list[str] | None = None
    preferred_cuisine: str | None = None
    preferred_complexity: str | None = None
    time_limit_minutes: int | None = None

    def prompt_text(self) -> str:
        goal_text = {
            "lose": "похудение",
            "maintain": "поддержание",
            "gain": "набор",
            None: "не указана",
        }[self.goal]
        allergies = ", ".join(self.allergies or []) or "нет"
        excluded = ", ".join(self.excluded_products or []) or "нет"
        cuisine = self.preferred_cuisine or "не указана"
        complexity = self.preferred_complexity or "не указана"
        time_limit = (
            f"{self.time_limit_minutes} минут"
            if self.time_limit_minutes is not None
            else "не указан"
        )
        return (
            f"цель: {goal_text}; "
            f"аллергии: {allergies}; "
            f"исключить продукты: {excluded}; "
            f"кухня: {cuisine}; "
            f"сложность: {complexity}; "
            f"лимит времени: {time_limit}"
        )


class RecipeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_user(self, tg_user_id: int, username: str | None = None) -> User:
        user = await self.session.scalar(select(User).where(User.tg_user_id == tg_user_id))
        if user:
            if username and user.username != username:
                user.username = username
                await self.session.flush()
            return user

        user = User(tg_user_id=tg_user_id, username=username)
        self.session.add(user)
        await self.session.flush()
        return user

    async def save_recipe(
        self,
        user_id: int,
        request_type: RequestType,
        source_ingredients: list[str],
        supplemented_ingredients: list[str],
        llm_response: dict[str, Any],
    ) -> Recipe:
        recipe = Recipe(
            user_id=user_id,
            request_type=request_type,
            source_ingredients=source_ingredients,
            supplemented_ingredients=supplemented_ingredients,
            llm_response=llm_response,
            title=llm_response.get("title"),
            time_minutes=llm_response.get("time_minutes"),
            servings=llm_response.get("servings"),
            plate_map=llm_response.get("plate_map", {}),
        )
        self.session.add(recipe)
        await self.session.flush()
        return recipe

    async def set_vote(self, user_id: int, recipe_id: int, vote: Literal[-1, 1]) -> RecipeVote:
        existing_vote = await self.session.scalar(
            select(RecipeVote).where(RecipeVote.user_id == user_id, RecipeVote.recipe_id == recipe_id)
        )
        if existing_vote:
            existing_vote.vote = vote
            await self.session.flush()
            return existing_vote

        new_vote = RecipeVote(user_id=user_id, recipe_id=recipe_id, vote=vote)
        self.session.add(new_vote)
        await self.session.flush()
        return new_vote

    async def get_rating(self, recipe_id: int) -> int:
        rating = await self.session.scalar(
            select(func.coalesce(func.sum(RecipeVote.vote), 0)).where(RecipeVote.recipe_id == recipe_id)
        )
        return int(rating or 0)

    async def add_favorite(self, user_id: int, recipe_id: int) -> UserFavorite:
        favorite = await self.session.scalar(
            select(UserFavorite).where(
                UserFavorite.user_id == user_id,
                UserFavorite.recipe_id == recipe_id,
            )
        )
        if favorite:
            return favorite

        favorite = UserFavorite(user_id=user_id, recipe_id=recipe_id)
        self.session.add(favorite)
        await self.session.flush()
        return favorite

    async def remove_favorite(self, user_id: int, recipe_id: int) -> bool:
        favorite = await self.session.scalar(
            select(UserFavorite).where(
                UserFavorite.user_id == user_id,
                UserFavorite.recipe_id == recipe_id,
            )
        )
        if not favorite:
            return False

        await self.session.delete(favorite)
        await self.session.flush()
        return True

    def get_top_recipes_query(self, limit: int = 10) -> Select[tuple[Recipe, int]]:
        rating = func.coalesce(func.sum(RecipeVote.vote), 0).label("rating")
        return (
            select(Recipe, rating)
            .outerjoin(RecipeVote, RecipeVote.recipe_id == Recipe.id)
            .group_by(Recipe.id)
            .order_by(rating.desc(), Recipe.created_at.desc())
            .limit(limit)
        )

    async def get_user_liked_recipe_ids(self, user_id: int) -> set[int]:
        rows = await self.session.scalars(
            select(RecipeVote.recipe_id).where(RecipeVote.user_id == user_id, RecipeVote.vote == 1)
        )
        return set(rows.all())

    async def get_user_favorite_recipe_ids(self, user_id: int) -> set[int]:
        rows = await self.session.scalars(
            select(UserFavorite.recipe_id).where(UserFavorite.user_id == user_id)
        )
        return set(rows.all())

    async def get_recipe_with_rating(self, recipe_id: int) -> RecipeWithRating | None:
        rating = func.coalesce(func.sum(RecipeVote.vote), 0).label("rating")
        row = await self.session.execute(
            select(Recipe, rating)
            .outerjoin(RecipeVote, RecipeVote.recipe_id == Recipe.id)
            .where(Recipe.id == recipe_id)
            .group_by(Recipe.id)
        )
        item = row.one_or_none()
        if item is None:
            return None
        recipe, recipe_rating = item
        return RecipeWithRating(recipe=recipe, rating=int(recipe_rating or 0))

    async def list_recipes_with_rating(self, scope: BrowseScope, viewer_user_id: int) -> list[RecipeWithRating]:
        rating = func.coalesce(func.sum(RecipeVote.vote), 0).label("rating")
        query = (
            select(Recipe, rating)
            .outerjoin(RecipeVote, RecipeVote.recipe_id == Recipe.id)
            .group_by(Recipe.id)
        )
        if scope == "favorites":
            query = query.join(UserFavorite, UserFavorite.recipe_id == Recipe.id).where(
                UserFavorite.user_id == viewer_user_id
            )
            query = query.order_by(Recipe.created_at.desc())
        elif scope == "history":
            query = query.where(Recipe.user_id == viewer_user_id).order_by(Recipe.created_at.desc())
        else:
            query = query.order_by(rating.desc(), Recipe.created_at.desc())

        rows = await self.session.execute(query)
        result: list[RecipeWithRating] = []
        for recipe, recipe_rating in rows.all():
            result.append(RecipeWithRating(recipe=recipe, rating=int(recipe_rating or 0)))
        return result

    async def get_user_settings(self, user_id: int) -> UserSettings:
        user = await self.session.get(User, user_id)
        if user is None:
            return UserSettings()
        goal: GoalType | None = None
        if user.goal in ("lose", "maintain", "gain"):
            goal = user.goal
        return UserSettings(
            goal=goal,
            allergies=list(user.allergies or []),
            excluded_products=list(user.excluded_products or []),
            preferred_cuisine=user.preferred_cuisine,
            preferred_complexity=user.preferred_complexity,
            time_limit_minutes=user.time_limit_minutes,
        )

    async def update_user_settings(
        self,
        user_id: int,
        *,
        goal: GoalType | None | object = ...,
        allergies: list[str] | None | object = ...,
        excluded_products: list[str] | None | object = ...,
        preferred_cuisine: str | None | object = ...,
        preferred_complexity: str | None | object = ...,
        time_limit_minutes: int | None | object = ...,
    ) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")

        if goal is not ...:
            user.goal = goal
        if allergies is not ...:
            user.allergies = allergies or []
        if excluded_products is not ...:
            user.excluded_products = excluded_products or []
        if preferred_cuisine is not ...:
            user.preferred_cuisine = preferred_cuisine
        if preferred_complexity is not ...:
            user.preferred_complexity = preferred_complexity
        if time_limit_minutes is not ...:
            user.time_limit_minutes = time_limit_minutes

        await self.session.flush()
        return user
