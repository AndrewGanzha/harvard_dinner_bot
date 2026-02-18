from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards.main_menu import main_menu_inline_keyboard, main_menu_keyboard
from bot.states import UserMode

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(UserMode.main_menu)
    await message.answer(
        "Привет! Я бот «Гарвардская тарелка». Выберите режим работы.",
        reply_markup=main_menu_keyboard(),
    )
    await message.answer(
        "Также можно использовать inline-меню:",
        reply_markup=main_menu_inline_keyboard(),
    )


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/start - открыть главное меню\n"
        "/help - помощь\n\n"
        "Используйте кнопки меню для навигации."
    )
