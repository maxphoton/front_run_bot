"""
Router for orders management commands.
Handles viewing and managing user orders.
"""

import logging
from typing import Union

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_dialog import DialogManager, StartMode
from service.database import get_user, get_user_accounts

from routers.orders_dialog import OrdersSG

logger = logging.getLogger(__name__)

# ============================================================================
# Router and handlers
# ============================================================================

orders_manage_router = Router()


async def start_orders(
    event: Union[Message, CallbackQuery], dialog_manager: DialogManager
) -> None:
    """Shared entry: start orders/portfolio flow (from command or menu callback)."""
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
        await dialog_manager.start(
            OrdersSG.orders_list,
            data={"account_id": account_id},
            mode=StartMode.RESET_STACK,
        )
        if isinstance(event, CallbackQuery):
            await event.answer()
        return

    builder = InlineKeyboardBuilder()
    for account in accounts:
        wallet = account["wallet_address"]
        acc_id = account["account_id"]
        builder.button(
            text=f"Account {acc_id} ({wallet[:8]}...)",
            callback_data=f"orders_account_{acc_id}",
        )
    builder.button(text="✖️ Cancel", callback_data="cancel_orders")
    builder.adjust(1)

    text = """<tg-emoji emoji-id="5258503720928288433">📋</tg-emoji> View Orders

Select an account to view orders:"""
    if isinstance(event, Message):
        await event.answer(text, reply_markup=builder.as_markup())
    else:
        await event.message.edit_text(text, reply_markup=builder.as_markup())
        await event.answer()


@orders_manage_router.message(Command("orders"))
async def cmd_orders(message: Message, dialog_manager: DialogManager):
    """Обработчик команды /orders - просмотр ордеров пользователя."""
    logger.info(f"Команда /orders от пользователя {message.from_user.id}")
    await start_orders(message, dialog_manager)


@orders_manage_router.callback_query(F.data == "menu_orders")
async def menu_orders(callback: CallbackQuery, dialog_manager: DialogManager):
    """Main menu: start orders/portfolio flow."""
    await start_orders(callback, dialog_manager)


@orders_manage_router.callback_query(F.data.startswith("orders_account_"))
async def process_orders_account_selection(
    callback: CallbackQuery, dialog_manager: DialogManager
):
    """Handles account selection for orders dialog."""
    account_id_str = callback.data.replace("orders_account_", "")
    try:
        account_id = int(account_id_str)
    except ValueError:
        await callback.answer("Invalid account ID", show_alert=True)
        return

    # Запускаем диалог с передачей account_id
    await callback.message.delete()
    await dialog_manager.start(
        OrdersSG.orders_list,
        data={"account_id": account_id},
        mode=StartMode.RESET_STACK,
    )
    await callback.answer()


@orders_manage_router.callback_query(F.data == "cancel_orders")
async def cancel_orders_selection(callback: CallbackQuery):
    """Handles canceling orders account selection."""
    await callback.message.edit_text("❌ Order viewing cancelled.")
    await callback.answer()
