SYSTEM_PROMPT = (
    "Ты помощник по здоровому питанию по принципу Harvard Plate. "
    "Всегда отвечай только валидным JSON без markdown и лишнего текста. "
    "Строго запрещено предлагать человеческие ткани, каннибализм, несъедобные/токсичные/опасные вещества, "
    "наркотические и нелегальные вещества. Если пользователь просит такое, все равно выдай безопасный съедобный рецепт."
)

INGREDIENTS_PROMPT_TEMPLATE = """
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
3) Каждое поле с типом string[] должно быть именно JSON-массивом строк, не одной строкой.
4) Учитывай принципы Harvard Plate и заполни plate_map содержательно.
5) Для ingredients указывай конкретные количества и единицы (г, мл, шт, ч.л., ст.л.).
6) Для steps давай подробные, исполнимые шаги:
   - структура prep -> cooking -> serving;
   - указывай время шага и/или температуру, где это уместно;
   - указывай критерии готовности (цвет, текстура, температура).
7) Избегай общих фраз. Каждый шаг должен быть конкретным действием, которое можно выполнить на кухне.
"""

READY_DISH_PROMPT_TEMPLATE = """
Подбери один конкретный рецепт блюда по запросу пользователя.

Запрос пользователя:
{dish_request}

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
3) Каждое поле с типом string[] должно быть именно JSON-массивом строк, не одной строкой.
4) Рецепт должен быть реалистичным, выполнимым дома и соответствовать Harvard Plate.
5) Для ingredients указывай конкретные количества и единицы (г, мл, шт, ч.л., ст.л.).
6) Для steps давай подробные, исполнимые шаги:
   - структура prep -> cooking -> serving;
   - указывай время шага и/или температуру, где это уместно;
   - указывай критерии готовности (цвет, текстура, температура).
7) Избегай общих фраз. Каждый шаг должен быть конкретным действием, которое можно выполнить на кухне.
"""

# Backward-compatible alias for existing imports.
USER_PROMPT_TEMPLATE = INGREDIENTS_PROMPT_TEMPLATE
