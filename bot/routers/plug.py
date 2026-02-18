"""
Router for handling unknown messages (fallback handler).
Shows main menu with colored inline buttons.
"""

from aiogram import Router
from aiogram.types import Message

from routers.start import send_main_menu

plug_router = Router()


@plug_router.message()
async def handle_unknown_message(message: Message):
    """Show main menu with inline buttons for unmatched messages."""
    await send_main_menu(message)
