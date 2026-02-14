"""
Router for handling unknown messages (fallback handler).
Shows main menu with colored inline buttons.
"""

from aiogram import Router
from aiogram.types import Message

from routers.start import MAIN_MENU_PREFIX, build_main_menu_keyboard

plug_router = Router()


@plug_router.message()
async def handle_unknown_message(message: Message):
    """Show main menu with inline buttons for unmatched messages."""
    await message.answer(
        MAIN_MENU_PREFIX + "Main menu",
        reply_markup=build_main_menu_keyboard().as_markup(),
    )
