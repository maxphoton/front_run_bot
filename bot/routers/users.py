"""
Router for user commands.
Handles help, support, and account checking commands.
"""

import logging
from datetime import datetime
from typing import Union

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, LinkPreviewOptions, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from opinion.client_factory import create_client
from opinion.opinion_api_wrapper import (
    ORDER_STATUS_PENDING,
    get_my_orders,
    get_my_positions,
    get_usdt_balance,
)
from service.config import settings
from service.database import (
    get_opinion_account,
    get_user,
    get_user_accounts,
    update_proxy_status,
)
from service.proxy_checker import check_proxy_health

from routers.start import MAIN_MENU_PREFIX, build_main_menu_keyboard

logger = logging.getLogger(__name__)

# ============================================================================
# States for support command
# ============================================================================


class SupportStates(StatesGroup):
    """States for support message."""

    waiting_support_message = State()


# ============================================================================
# Router and handlers
# ============================================================================

user_router = Router()


def _message_from_event(event: Union[Message, CallbackQuery]) -> Message:
    """Get Message from either Message or CallbackQuery."""
    return event if isinstance(event, Message) else event.message


async def start_check_profile(event: Union[Message, CallbackQuery]) -> None:
    """Shared entry: start check profile flow (from command or menu callback)."""
    telegram_id = event.from_user.id
    user = await get_user(telegram_id)
    if not user:
        err = """❌ You are not registered. Use /start to register first."""
        if isinstance(event, Message):
            await event.answer(err)
        else:
            await event.message.edit_text(err)
            await event.answer()
        return

    accounts = await get_user_accounts(telegram_id)
    if not accounts:
        err = """❌ You don't have any Opinion profiles yet.

Use /start to add your first Opinion profile."""
        if isinstance(event, Message):
            await event.answer(err)
        else:
            await event.message.edit_text(err)
            await event.answer()
        return

    if len(accounts) == 1:
        account_id = accounts[0]["account_id"]
        await show_account_info(_message_from_event(event), account_id)
        if isinstance(event, CallbackQuery):
            await event.answer()
        return

    builder = InlineKeyboardBuilder()
    for account in accounts:
        wallet = account["wallet_address"]
        acc_id = account["account_id"]
        builder.button(
            text=f"Account {acc_id} ({wallet[:8]}...)",
            callback_data=f"check_account_{acc_id}",
        )
    builder.button(text="✖️ Cancel", callback_data="cancel_check_account")
    builder.adjust(1)

    text = """📊 Check Account

Select an account to view statistics:"""
    if isinstance(event, Message):
        await event.answer(text, reply_markup=builder.as_markup())
    else:
        await event.message.edit_text(text, reply_markup=builder.as_markup())
        await event.answer()


@user_router.message(Command("check_profile"))
async def cmd_check_account(message: Message):
    """Обработчик команды /check_profile - статистика по аккаунту."""
    logger.info(f"Команда /check_profile от пользователя {message.from_user.id}")
    await start_check_profile(message)


@user_router.callback_query(F.data == "menu_check_profile")
async def menu_check_profile(callback: CallbackQuery):
    """Main menu: start check profile flow."""
    await start_check_profile(callback)


@user_router.callback_query(F.data.startswith("check_account_"))
async def process_check_account_selection(callback: CallbackQuery):
    """Handles account selection for check_profile command."""
    account_id_str = callback.data.replace("check_account_", "")
    try:
        account_id = int(account_id_str)
    except ValueError:
        await callback.answer("Invalid account ID", show_alert=True)
        return

    await callback.message.delete()
    await show_account_info(callback.message, account_id)
    await callback.answer()


@user_router.callback_query(F.data == "cancel_check_account")
async def cancel_check_account_selection(callback: CallbackQuery):
    """Handles canceling check_profile selection."""
    await callback.message.edit_text("❌ Account check cancelled.")
    await callback.answer()


async def show_account_info(message: Message, account_id: int):
    """Shows account information for the selected account."""
    try:
        # Получаем данные аккаунта
        account = await get_opinion_account(account_id)
        if not account:
            await message.answer("❌ Account not found.")
            return

        # Создаем клиент
        client = create_client(account)

        # Получаем данные аккаунта
        balance = await get_usdt_balance(client)
        open_orders = await get_my_orders(client, status=ORDER_STATUS_PENDING)
        positions = await get_my_positions(client, limit=100)

        # Подсчитываем количество открытых ордеров
        open_orders_count = len(open_orders) if open_orders else 0

        # Подсчитываем количество позиций
        positions_count = len(positions) if positions else 0

        # Вычисляем общую стоимость позиций
        total_value = 0.0
        if positions:
            for position in positions:
                try:
                    value_str = getattr(position, "current_value_in_quote_token", "0")
                    value = float(value_str) if value_str else 0.0
                    total_value += value
                except (ValueError, TypeError) as e:
                    logger.warning(f"Ошибка при парсинге стоимости позиции: {e}")
                    continue

        # Информация о прокси - проверяем реально
        proxy_info = ""
        use_proxy = False
        if use_proxy:
            if account.get("proxy_str"):
                proxy_str = account["proxy_str"]
                proxy_parts = proxy_str.split(":")
                proxy_info = f"\n\n🔐 Proxy: {proxy_parts[0]}:{proxy_parts[1]}"

                # Выполняем реальную проверку прокси
                logger.info(f"Проверка прокси для аккаунта {account_id}")
                proxy_status = await check_proxy_health(proxy_str)

                # Обновляем статус в БД с текущим временем
                current_time = datetime.now().isoformat()
                await update_proxy_status(account_id, proxy_status, current_time)

                status_emoji = {"working": "✅", "failed": "❌", "unknown": "❓"}.get(
                    proxy_status, "❓"
                )
                proxy_info += f" {status_emoji} ({proxy_status})"
                proxy_info += f"\n🕒 Last check: {current_time[:16]}"
            else:
                proxy_info = "\n\n🔐 Proxy: Not configured"

        wallet = account["wallet_address"]

        # Формируем сообщение
        account_info = f"""📊 <b>Profile Statistics</b>

🆔 Account ID: {account_id}
💼 Wallet: <code>{wallet}</code>
💰 USDT Balance: {balance:.6f} USDT
📋 Count open orders: {open_orders_count}
📈 Open Positions: {positions_count}
💵 Total Value in Positions: {total_value:.6f} USDT{proxy_info}

You may see all orders by command '/orders'"""

        await message.answer(
            account_info,
            parse_mode=ParseMode.HTML,
            reply_markup=_build_help_keyboard().as_markup(),
        )

    except Exception as e:
        logger.error(f"Ошибка при получении статистики аккаунта {account_id}: {e}")
        await message.answer(
            """❌ Failed to get account information. Please try again later."""
        )


HELP_DOC_URL = "https://bidask-bot.gitbook.io/docs/"

HELP_MESSAGE = (
    "For information and instructions - see documentation: "
    f'<a href="{HELP_DOC_URL}">https://bidask-bot.gitbook.io/docs/</a>'
)


def _build_help_keyboard() -> InlineKeyboardBuilder:
    """Help message keyboard with Main menu button."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Main menu", callback_data="show_main_menu")
    return builder


async def send_help_content(event: Union[Message, CallbackQuery]) -> None:
    """Send short help with doc link (from command or menu callback). Link preview disabled."""
    link_preview = LinkPreviewOptions(is_disabled=True)
    markup = _build_help_keyboard().as_markup()
    if isinstance(event, Message):
        await event.answer(
            HELP_MESSAGE,
            parse_mode=ParseMode.HTML,
            link_preview_options=link_preview,
            reply_markup=markup,
        )
    else:
        await event.message.edit_text(
            HELP_MESSAGE,
            parse_mode=ParseMode.HTML,
            link_preview_options=link_preview,
            reply_markup=markup,
        )
        await event.answer()


@user_router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help - ссылка на документацию."""
    logger.info(f"Команда /help от пользователя {message.from_user.id}")
    await send_help_content(message)


@user_router.callback_query(F.data == "menu_help")
async def menu_help(callback: CallbackQuery):
    """Main menu: show help (doc link)."""
    await send_help_content(callback)


@user_router.callback_query(F.data == "show_main_menu")
async def show_main_menu(callback: CallbackQuery):
    """From help (or other): show main menu with buttons."""
    await callback.message.edit_text(
        MAIN_MENU_PREFIX + "Main menu",
        reply_markup=build_main_menu_keyboard().as_markup(),
    )
    await callback.answer()


@user_router.message(Command("support"))
async def cmd_support(message: Message, state: FSMContext):
    """Обработчик команды /support - отправка сообщения в поддержку."""
    logger.info(f"Команда /support от пользователя {message.from_user.id}")
    await message.answer(
        """💬 <b>Support</b>

Please describe your question or issue. You can send text or a photo with a caption.

Your message will be forwarded to the administrator."""
    )
    await state.set_state(SupportStates.waiting_support_message)


@user_router.message(SupportStates.waiting_support_message)
async def process_support_message(message: Message, state: FSMContext):
    """Обработчик сообщения поддержки - пересылает админу."""
    # Проверяем, что админ указан
    if not settings.admin_telegram_id or settings.admin_telegram_id == 0:
        await message.answer(
            """❌ Support is not available. Administrator is not configured."""
        )
        await state.clear()
        return

    try:
        # Получаем бота из сообщения
        bot = message.bot

        # Формируем информацию о пользователе
        user_info = "<b>Support message from:</b>\n"
        user_info += f"• User ID: <code>{message.from_user.id}</code>\n"
        if message.from_user.username:
            user_info += f"• Username: @{message.from_user.username}\n"

        # Если есть фото
        if message.photo:
            # Отправляем фото с подписью админу
            caption = (
                f"{user_info}\n{message.caption or ''}"
                if message.caption
                else user_info
            )
            await bot.send_photo(
                chat_id=settings.admin_telegram_id,
                photo=message.photo[-1].file_id,  # Берем фото наибольшего размера
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
        else:
            # Отправляем текстовое сообщение админу
            full_message = f"{user_info}\n\n<b>Message:</b>\n{message.text}"
            await bot.send_message(
                chat_id=settings.admin_telegram_id,
                text=full_message,
                parse_mode=ParseMode.HTML,
            )

        # Подтверждаем пользователю
        await message.answer(
            """✅ Your message has been sent to support. We will get back to you soon!"""
        )

        logger.info(
            f"Support message from user {message.from_user.id} forwarded to admin"
        )

    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения поддержки: {e}")
        await message.answer(
            """❌ Failed to send your message. Please try again later."""
        )
    finally:
        await state.clear()
