"""
Router for user registration flow (/start command).
Handles the registration process - invite code optional via settings.
"""

import logging
import re
from pathlib import Path
from typing import Union

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from service.config import settings
from service.database import get_user, get_user_accounts, save_user

from routers.account import start_add_account_flow
from routers.invites import is_invite_valid, use_invite

logger = logging.getLogger(__name__)

# Home emoji prefix for main menu messages
MAIN_MENU_PREFIX = """<tg-emoji emoji-id="5257963315258204021">🏠</tg-emoji> """

MAIN_MENU_CAPTION = MAIN_MENU_PREFIX + "Main menu"
MENU_IMAGE_PATH = Path(__file__).resolve().parent.parent.parent / "files" / "menu.png"

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

📚 Docs: https://opinionbot.gitbook.io/documentation/"""
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
📚 Docs: https://opinionbot.gitbook.io/documentation/"""
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
    # Row 1: Always-first (blue); Row 2: Market, Limit (blue); Row 3: Portfolio, Help (gray)
    builder.button(
        text="Always-first Order",
        callback_data="menu_limit_first",
        icon_custom_emoji_id="5258185631355378853",
        style="primary",
    )
    builder.button(
        text="Market Order",
        callback_data="menu_market",
        icon_custom_emoji_id="5258330865674494479",
        style="primary",
    )
    builder.button(
        text="Limit Order",
        callback_data="menu_limit",
        icon_custom_emoji_id="5257965174979042426",
        style="primary",
    )
    builder.button(
        text="Portfolio",
        callback_data="menu_check_profile",
        icon_custom_emoji_id="5258011929993026890",
    )
    builder.button(
        text="Help",
        callback_data="menu_help",
        icon_custom_emoji_id="5258503720928288433",
    )
    builder.adjust(1, 2, 2)  # 1 + 2 + 2 rows
    return builder


async def send_main_menu(
    event: Union[Message, CallbackQuery],
    *,
    edit: bool = False,
) -> None:
    """Send main menu as photo with caption and keyboard. Use edit=True to replace current message (callback only)."""
    markup = build_main_menu_keyboard().as_markup()
    photo = FSInputFile(MENU_IMAGE_PATH)
    if isinstance(event, Message):
        await event.answer_photo(
            photo=photo,
            caption=MAIN_MENU_CAPTION,
            reply_markup=markup,
        )
    else:
        await event.answer()
        if edit:
            media = InputMediaPhoto(media=photo, caption=MAIN_MENU_CAPTION)
            await event.message.edit_media(media=media, reply_markup=markup)
        else:
            await event.message.answer_photo(
                photo=photo,
                caption=MAIN_MENU_CAPTION,
                reply_markup=markup,
            )


# ============================================================================
# Router and handlers
# ============================================================================

start_router = Router()


@start_router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handler for /start command - start of registration process."""
    logger.info(f"Команда /start от пользователя {message.from_user.id}")
    telegram_id = message.from_user.id
    user = await get_user(telegram_id)
    accounts = await get_user_accounts(telegram_id)

    # Show main menu only when user exists and has at least one Opinion account
    if user and accounts:
        await send_main_menu(message)
        return

    # New user (not in DB)
    if not settings.invite_required:
        await save_user(
            telegram_id=telegram_id,
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
📚 Docs: https://opinionbot.gitbook.io/documentation/

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
