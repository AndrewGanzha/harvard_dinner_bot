from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Recipe, RecipeVote, User, UserFavorite

RequestType = Literal["ingredients", "random"]


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
