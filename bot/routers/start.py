"""
Router for user registration flow (/start command).
Handles the registration process - invite code optional via settings.
"""

import logging
import re

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from service.config import settings
from service.database import get_user, save_user

from routers.account import start_add_account_flow
from routers.invites import is_invite_valid, use_invite

logger = logging.getLogger(__name__)

# Home emoji prefix for main menu messages
MAIN_MENU_PREFIX = "🏠 "

# Shared completion message (no /floating_order)
REGISTRATION_COMPLETED_MSG = (
    MAIN_MENU_PREFIX
    + """✅ Registration Completed!

Now you need to add your Opinion profile.

Step 2: Use the /add_profile to add your first Opinion profile with wallet address, private key, and API key.

After adding an account, you can:
• Use /market to place a market order.
• Use /limit to place a limit order.
• Use /limit_first command for keeps your limit orders always first in the order book.
• Use /orders to manage your orders.
• Use /check_profile to view profile statistics.
• Use /profile_list to view all your profiles.
• Use /help to view instructions.
• Use /support to contact administrator.

📚 Docs: https://bidask-bot.gitbook.io/docs/"""
)

WELCOME_REGISTERED_MSG = (
    MAIN_MENU_PREFIX
    + """✅ You are already registered!

Use the menu below or:
Use the /market to place a market order.
Use the /limit to place a limit order.
Use the /limit_first command for keeps your limit orders always first in the order book.
Use the /orders to manage your orders.
Use the /check_profile to view profile statistics.
Use the /profile_list to view all your profiles.
Use the /help to view instructions.
Use the /support to contact administrator.

🚀 Subscribe for best strategies, updates and VIP access @cmchn_public
📚 Docs: https://bidask-bot.gitbook.io/docs/"""
)

# ============================================================================
# States for user registration
# ============================================================================


class RegistrationStates(StatesGroup):
    """States for the registration process."""

    waiting_invite = State()


# ============================================================================
# Main menu keyboard
# ============================================================================


def build_main_menu_keyboard() -> InlineKeyboardBuilder:
    """Build main menu with inline buttons. Portfolio runs check_profile."""
    builder = InlineKeyboardBuilder()
    # style: Bot API 9.4 — primary (blue), success (green), danger (red)
    builder.button(
        text="📊 Market order",
        callback_data="menu_market",
        style="primary",
    )
    builder.button(
        text="📈 Limit order",
        callback_data="menu_limit",
        style="danger",
    )
    builder.button(
        text="🥇 Always-first order",
        callback_data="menu_limit_first",
        style="danger",
    )
    builder.button(
        text="📋 Portfolio",
        callback_data="menu_check_profile",
        style="primary",
    )
    builder.button(
        text="❓ Help",
        callback_data="menu_help",
        style="success",
    )
    builder.adjust(2, 2, 1)  # 2+2+1 rows
    return builder


# ============================================================================
# Router and handlers
# ============================================================================

start_router = Router()


@start_router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handler for /start command - start of registration process."""
    logger.info(f"Команда /start от пользователя {message.from_user.id}")
    user = await get_user(message.from_user.id)

    if user:
        await message.answer(
            MAIN_MENU_PREFIX + "Main menu",
            reply_markup=build_main_menu_keyboard().as_markup(),
        )
        return

    if not settings.invite_required:
        await save_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username.strip()
            if message.from_user.username
            else None,
        )
        await state.clear()
        await start_add_account_flow(message, state)
        return

    await message.answer(
        """ Welcome!
🚀 Subscribe for best strategies, updates and VIP access @cmchn_public
📚 Docs: https://bidask-bot.gitbook.io/docs/

🔐 Step 1: Bot Registration

To register, you need an invite code.

Please enter your invite code:"""
    )
    await state.set_state(RegistrationStates.waiting_invite)


@start_router.message(RegistrationStates.waiting_invite)
async def process_invite(message: Message, state: FSMContext):
    """Handles invite code input and completes registration."""
    invite_code = message.text.strip()

    # Проверяем формат (латиница и цифры)
    if not re.match(r"^[A-Za-z0-9]{10}$", invite_code):
        await message.answer(
            """❌ Invalid invite code format. 
            
Please try again:"""
        )
        return

    # Проверяем валидность инвайта
    if not await is_invite_valid(invite_code):
        await message.answer(
            """❌ Invalid or already used invite code.

Please enter a valid invite code:"""
        )
        return

    telegram_id = message.from_user.id

    # Используем инвайт (атомарно, с проверкой валидности внутри)
    if not await use_invite(invite_code, telegram_id):
        await state.clear()
        await message.answer(
            """❌ Registration failed: The invite code could not be used.

Please start registration again with /start using a valid invite code."""
        )
        return

    # Сохраняем пользователя в БД (только telegram_id и username)
    await save_user(
        telegram_id=telegram_id,
        username=message.from_user.username.strip()
        if message.from_user.username
        else None,
    )

    # Удаляем сообщение пользователя с инвайт-кодом
    try:
        await message.delete()
    except Exception:
        pass

    await state.clear()
    await message.answer(
        REGISTRATION_COMPLETED_MSG,
        reply_markup=build_main_menu_keyboard().as_markup(),
    )
