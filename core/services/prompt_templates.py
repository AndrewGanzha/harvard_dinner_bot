SYSTEM_PROMPT = (
    "Ты помощник по здоровому питанию по принципу Harvard Plate. "
    "Всегда отвечай только валидным JSON без markdown и лишнего текста."
)

USER_PROMPT_TEMPLATE = """
Сформируй рецепт из ингредиентов пользователя.

Входные ингредиенты:
{ingredients}

Недостающие группы тарелки:
{missing_groups}

Пожелания пользователя:
{user_preferences}

Требования к JSON-ответу:
1) Только JSON-объект.
2) Поля:
   - title: string
   - ingredients: string[]
   - steps: string[]
   - time_minutes: int
   - servings: int
   - plate_map: object с ключами veggies_fruits, whole_grains, proteins, fats, dairy(optional), others
   - nutrition: object | null
   - tips: string[]
3) Учитывай принципы Harvard Plate и заполни plate_map содержательно.
"""
