from aiogram.fsm.state import State, StatesGroup


class UserMode(StatesGroup):
    main_menu = State()
    entering_ingredients = State()
    choosing_ready_dish = State()
    viewing_top = State()
    viewing_favorites = State()
    editing_settings = State()
