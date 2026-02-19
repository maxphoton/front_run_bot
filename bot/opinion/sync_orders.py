"""
Script for automatic order synchronization and repositioning.
Maintains a constant offset (in ticks) between the current market price and the order's target price.

PROCESS OVERVIEW:
================

1. MAIN LOOP (async_sync_all_orders):
   - Retrieves all users from the database
   - For each user, processes their active orders sequentially
   - Outputs final statistics (cancelled, placed, errors)
   - Each user is processed independently with their own API client

2. ORDER STATUS CHECK (process_user_orders):
   For each active order from database:
   a. Checks order status via API (get_order_by_id):
      - Compares database status ('pending') with API status
      - If status changed from 'pending' to 'Finished' (finished):
        * Updates database status to 'finished'
        * Sends notification to user with order details from API (price, market link, etc.)
        * Skips further processing (order is no longer pending)
      - If status changed from 'pending' to 'Canceled' (canceled):
        * Updates database status to 'canceled'
        * Skips further processing (no notification sent for canceled orders)
      - If status check fails, continues with normal processing (graceful degradation)

3. ORDER PROCESSING (process_user_orders):
   For each active order (after status check):
   a. Gets current market price from orderbook:
      - For BUY orders: uses best_bid (highest bid price)
        When price goes DOWN (best_bid decreases), order gets closer to execution
      - For SELL orders: uses best_bid (highest bid price)
        When price goes UP (best_bid increases), order gets closer to execution
   b. Calculates new target price using saved offset_ticks from database:
      - BUY: new_target_price = current_price - (offset_ticks * TICK_SIZE)
      - SELL: new_target_price = current_price + (offset_ticks * TICK_SIZE)
      - Price is clamped to [0.001, 0.999] range (API requirement)
   c. Calculates target price change in cents:
      target_price_change_cents = abs(new_target_price - old_target_price) * 100
   d. Checks if change is sufficient using reposition_threshold_cents:
      * If change >= threshold: adds order_id to cancellation list AND new order params to placement list
        (both lists updated simultaneously to maintain consistency)
      * If change < threshold: skips repositioning (saves API calls and gas fees)
   e. Adds price change notification to list ONLY if order will be repositioned

4. NOTIFICATIONS (sent immediately after order processing):
   - Price change notifications are sent ONLY for orders that will be repositioned
   - Each notification indicates that the order will be repositioned
   - Includes: old/new current prices, old/new target prices, price change in cents,
     target price change in cents, offset, reposition threshold
   - Notifications sent BEFORE cancellation/placement to inform user immediately

5. ORDER CANCELLATION:
   - Cancels old orders in batch via API (only orders that need repositioning)
   - BATCHES ARE FORMED PER USER: all orders for one user are in the same batch
   - Checks success via result_data.errno == 0 from API response (not just success flag)
   - Logs each cancellation with User ID and Market ID for debugging
   - If ANY order fails to cancel, skips placement for ALL orders (safety check)

6. ORDER PLACEMENT:
   - Places new orders in batch ONLY if ALL old orders were successfully cancelled
   - BATCHES ARE FORMED PER USER: all orders for one user are in the same batch
   - Checks success via result_data.errno == 0 (not just success=True)
     According to API docs: result['success'] = True but result['result'].errno != 0 means failure
   - Logs each placement with User ID and Market ID for debugging
   - If placement fails for specific order (e.g., insufficient balance):
     * Sends error notification to user for THAT specific order (not for entire batch)
     * Notification includes old_order_id (cancelled), error code, and error message
     * Other orders in batch continue to be processed

7. DATABASE UPDATE:
   - Updates database ONLY for successfully placed orders (errno == 0)
   - Updates: order_id (old -> new), current_price, target_price
   - Sends success notification to user after database update
   - If placement failed, database is NOT updated (old order remains in DB as cancelled)

KEY FEATURES:
============
- Order status synchronization: Checks order status via API before processing
  * Automatically updates database when orders are filled or cancelled externally
  * Sends notifications for filled orders (with API data: price, market link, etc.)
  * Silently updates cancelled orders without notifications
- Uses offset_ticks from database (does not recalculate delta, preserves original offset)
- Uses reposition_threshold_cents from database (user-configurable per order, default 0.5 cents)
- Skips repositioning when change < threshold (saves API calls and gas fees)
- Sends price change notifications ONLY when order will be repositioned (reduces notification spam)
- Validates cancellation via errno == 0 (not just success flag)
- Validates placement via errno == 0 (handles cases where success=True but errno != 0)
- Places new orders only if ALL old orders cancelled successfully (safety check)
- Updates database only after successful placement (data consistency)
- Sends error notifications per order if placement fails (user awareness)
- Comprehensive logging with User ID and Market ID for debugging
- Performance monitoring: Logs start time, end time, and duration for each user's processing
- Visual formatting: boxed headers for start/end of sync task
- Runs as background task in bot, synchronizing orders every 60 seconds
- All blocking operations (API calls) wrapped in asyncio.to_thread() for non-blocking execution
- List consistency check: validates that cancellation and placement lists have same length
- Order identification: uses index matching between place_results and orders_to_place to identify failed orders
- Uses status constants (ORDER_STATUS_FINISHED, ORDER_STATUS_CANCELED) from opinion_api_wrapper for consistency

ARCHITECTURE:
============
- async_sync_all_orders(): Main async function used by bot (background task)
  * Logs processing time for each user (start, end, duration)
  * Uses try/except/finally to ensure time logging always happens
- main(): Synchronous function for standalone script execution (legacy, not used in bot)
- process_user_orders(): Processes all orders for one user, returns lists and notifications
  * Checks order status via API before processing (get_order_by_id)
  * Updates database and sends notifications for status changes
  * Calculates price changes and determines if repositioning is needed
- cancel_orders_batch(): Synchronous batch cancellation wrapper
- place_orders_batch(): Synchronous batch placement wrapper
- send_price_change_notification(): Sends price change notification to user
- send_order_updated_notification(): Sends success notification after DB update
- send_order_placement_error_notification(): Sends error notification if placement fails
- send_order_filled_notification(): Sends notification when order is filled
  * Uses API order object (not database dict) for accurate data
  * Includes filled price, market link to root market, and order details
"""

import asyncio
import logging
import time
import traceback
from html import escape
from typing import Dict, List, Optional, Tuple

from opinion.client_factory import create_client
from opinion.opinion_api_wrapper import (
    ORDER_STATUS_CANCELED,
    ORDER_STATUS_FINISHED,
    get_order_by_id,
)
from opinion_clob_sdk.chain.py_order_utils.model.order import PlaceOrderDataInput
from opinion_clob_sdk.chain.py_order_utils.model.order_type import LIMIT_ORDER
from opinion_clob_sdk.chain.py_order_utils.model.sides import OrderSide
from service.config import TICK_SIZE
from service.database import (
    get_account_orders,
    get_all_pending_orders_with_accounts,
    update_order_in_db,
    update_order_status,
)

logger = logging.getLogger(__name__)

# Прокси настраивается индивидуально для каждого аккаунта в create_client


def get_current_market_price(client, token_id: str, side: str) -> Optional[float]:
    """
    Получает текущую цену рынка для токена.

    Args:
        client: Клиент Opinion SDK
        token_id: ID токена (YES или NO)
        side: BUY или SELL - определяет, какую цену брать
              Для BUY и SELL используется best_bid (самый высокий бид):
              - BUY: когда цена ВНИЗ (best_bid уменьшается), ордер ближе к исполнению
              - SELL: когда цена ВВЕРХ (best_bid увеличивается), ордер ближе к исполнению

    Returns:
        Текущая цена или None в случае ошибки
    """
    try:
        response = client.get_orderbook(token_id=token_id)

        if response.errno != 0:
            logger.error(
                f"Ошибка получения orderbook для токена {token_id}: errno={response.errno}"
            )
            return None

        orderbook = (
            response.result
            if not hasattr(response.result, "data")
            else response.result.data
        )

        bids = orderbook.bids if hasattr(orderbook, "bids") else []

        # Для BUY и SELL используем best_bid (самый высокий бид)
        # BUY: когда цена ВНИЗ (best_bid уменьшается), ордер ближе к исполнению
        # SELL: когда цена ВВЕРХ (best_bid увеличивается), ордер ближе к исполнению
        if bids and len(bids) > 0:
            # Сортируем биды по убыванию цены
            bid_prices = []
            for bid in bids:
                if hasattr(bid, "price"):
                    try:
                        price = float(bid.price)
                        bid_prices.append(price)
                    except (ValueError, TypeError):
                        continue
            if bid_prices:
                return max(bid_prices)  # Самый высокий бид

        logger.warning(
            f"Не удалось определить текущую цену для токена {token_id}, side={side}"
        )
        return None

    except Exception as e:
        logger.error(f"Ошибка при получении текущей цены для токена {token_id}: {e}")
        return None


def get_market_url(market_id: int, root_market_id: Optional[int] = None) -> str:
    """
    Формирует ссылку на маркет.

    Args:
        market_id: ID маркета
        root_market_id: ID корневого маркета (для categorical markets), None для binary markets

    Returns:
        URL ссылка на маркет
    """
    if root_market_id is not None:
        # Категориальный маркет
        return f"https://app.opinion.trade/detail?topicId={root_market_id}&type=multi"
    else:
        # Бинарный маркет
        return f"https://app.opinion.trade/detail?topicId={market_id}"


def calculate_new_target_price(
    new_current_price: float, side: str, offset_ticks: int, tick_size: float = TICK_SIZE
) -> float:
    """
    Вычисляет новую целевую цену с использованием сохраненного offset_ticks.

    Использует ту же логику, что и при создании ордера.

    Args:
        new_current_price: Новая текущая цена рынка
        side: BUY или SELL
        offset_ticks: Отступ в тиках (из БД)
        tick_size: Размер тика (по умолчанию 0.001)

    Returns:
        Новая целевая цена
    """
    # Вычисляем целевую цену так же, как при создании ордера
    if side == "BUY":
        target = new_current_price - offset_ticks * tick_size
    else:  # SELL
        target = new_current_price + offset_ticks * tick_size

    # Ограничиваем диапазоном 0.001 - 0.999 (требования API)
    MIN_PRICE = 0.001
    MAX_PRICE = 0.999
    target = max(MIN_PRICE, min(MAX_PRICE, target))
    target = round(target, 3)

    # Проверяем, что после округления цена все еще в допустимом диапазоне
    if target < MIN_PRICE:
        target = MIN_PRICE
    elif target > MAX_PRICE:
        target = MAX_PRICE

    return target


async def process_account_orders(
    account_id: int, account_data: dict, bot=None, market_id: Optional[int] = None
) -> Tuple[List[str], List[Dict], List[Dict]]:
    """
    Обрабатывает ордера аккаунта и возвращает списки для отмены и размещения.

    Args:
        account_id: ID аккаунта Opinion
        account_data: Словарь с данными аккаунта (wallet_address, private_key, api_key, proxy_str, telegram_id)
        bot: Экземпляр aiogram Bot для отправки уведомлений (опционально)
        market_id: Фильтр по market_id. Если None, обрабатывает все ордера аккаунта.

    Returns:
        Tuple: (список order_id для отмены, список параметров новых ордеров, список уведомлений о смещении цены)
    """
    orders_to_cancel = []
    orders_to_place = []
    price_change_notifications = []  # Список уведомлений о смещении цены

    telegram_id = account_data.get("telegram_id")

    # Создаем клиент
    try:
        client = create_client(account_data)
    except Exception as e:
        logger.error(f"Ошибка создания клиента для аккаунта {account_id}: {e}")
        return orders_to_cancel, orders_to_place, price_change_notifications

    # Получаем активные ордера из БД
    db_orders = await get_account_orders(
        account_id, status="pending", market_id=market_id
    )

    if not db_orders:
        logger.info(f"У аккаунта {account_id} нет активных ордеров")
        return orders_to_cancel, orders_to_place, price_change_notifications

    logger.info(
        f"Обработка {len(db_orders)} активных ордеров для аккаунта {account_id} (пользователь {telegram_id})"
    )

    # Обрабатываем каждый ордер
    for db_order in db_orders:
        try:
            order_id = db_order.get("order_id")
            market_id = db_order.get("market_id")
            root_market_id = db_order.get(
                "root_market_id"
            )  # Для формирования ссылки на маркет
            token_id = db_order.get("token_id")  # Используем token_id из БД
            token_name = db_order.get("token_name")  # YES или NO
            side = db_order.get("side")  # BUY или SELL
            current_price_at_creation = db_order.get("current_price", 0.0)
            target_price = db_order.get("target_price", 0.0)
            offset_ticks = db_order.get("offset_ticks", 0)
            amount = db_order.get("amount", 0.0)
            reposition_threshold_cents = float(
                db_order.get("reposition_threshold_cents")
            )
            db_status = db_order.get("status")

            if not order_id or not market_id or not side or not token_id:
                logger.warning(f"Пропуск ордера с неполными данными: {order_id}")
                continue

            logger.info(f"--- Обрабатываем ордер {order_id} со статусом {db_status}")

            # Проверяем статус ордера через API
            # Если ордер был активным, а стал заполненным, обновляем БД и отправляем уведомление
            try:
                api_order = await get_order_by_id(client, order_id)
                if api_order:
                    # Получаем числовой статус из API и приводим к строке
                    api_status = str(getattr(api_order, "status", None))

                    logger.info(
                        f"Ордер {order_id} статус в API: {api_status} статус в БД: {db_status}"
                    )

                    # Если статус в БД был 'pending', а в API стал 'Finished' (finished)
                    if db_status == "pending" and api_status == ORDER_STATUS_FINISHED:
                        logger.info(
                            f"Ордер {order_id} был pending, теперь finished. Обновляем БД и отправляем уведомление."
                        )

                        # Обновляем статус в БД
                        await update_order_status(order_id, "finished")

                        # Отправляем уведомление пользователю
                        if bot:
                            await send_order_filled_notification(
                                bot, telegram_id, api_order
                            )

                        # Пропускаем дальнейшую обработку этого ордера
                        continue

                    # Если статус в БД был 'pending', а в API стал 'Canceled' (canceled)
                    elif db_status == "pending" and api_status == ORDER_STATUS_CANCELED:
                        logger.info(
                            f"Ордер {order_id} был pending, теперь canceled. Обновляем БД."
                        )

                        # Обновляем статус в БД
                        await update_order_status(order_id, "canceled")

                        # Пропускаем дальнейшую обработку этого ордера
                        continue
            except Exception as e:
                # Логируем только краткое сообщение, детали уже залогированы в opinion_api_wrapper
                error_str = str(e)
                is_timeout = (
                    "504" in error_str
                    or "Gateway Time-out" in error_str
                    or "timeout" in error_str.lower()
                )

                if is_timeout:
                    logger.info(
                        f"⏱️ Таймаут API при проверке статуса ордера {order_id}, продолжаем обработку без проверки статуса"
                    )
                else:
                    logger.warning(
                        f"Ошибка при проверке статуса ордера {order_id} через API: {e}"
                    )

                # Продолжаем обработку, если не удалось проверить статус (graceful degradation)

            # Если offset и threshold равны 0, не переставляем ордер (только контроль статуса)
            if offset_ticks == 0 and reposition_threshold_cents == 0:
                logger.info(
                    f"Пропуск перестановки ордера {order_id}: offset_ticks=0, "
                    f"reposition_threshold_cents=0"
                )
                continue

            # Получаем текущую цену рынка
            new_current_price = get_current_market_price(client, token_id, side)
            if not new_current_price:
                logger.warning(
                    f"Не удалось получить текущую цену для ордера {order_id}"
                )
                continue

            # Вычисляем новую целевую цену с использованием сохраненного offset_ticks
            new_target_price = calculate_new_target_price(
                new_current_price, side, offset_ticks
            )

            # Вычисляем изменение целевой цены в центах
            target_price_change = abs(new_target_price - target_price)
            target_price_change_cents = target_price_change * 100

            # Проверяем, достаточно ли изменение для перестановки ордера
            will_reposition = target_price_change_cents >= reposition_threshold_cents

            price_change = new_current_price - current_price_at_creation

            # Вычисляем ожидаемую целевую цену для старой текущей цены (для проверки)
            expected_old_target_price = calculate_new_target_price(
                current_price_at_creation, side, offset_ticks
            )

            logger.info(f"Цена изменилась для ордера {order_id}:")
            logger.info(f"  Account ID: {account_id} (User: {telegram_id})")
            logger.info(f"  Market ID: {market_id}")
            logger.info(f"  Token: {token_name} {side}")
            logger.info(f"  Старая текущая цена: {current_price_at_creation}")
            logger.info(f"  Новая текущая цена: {new_current_price}")
            logger.info(f"  Изменение текущей цены: {price_change:+.6f}")
            logger.info(f"  Старая целевая цена (из БД): {target_price}")
            logger.info(
                f"  Ожидаемая целевая цена (расчет): {expected_old_target_price:.6f}"
            )
            logger.info(f"  Новая целевая цена: {new_target_price}")
            logger.info(
                f"  Изменение целевой цены: {target_price_change:.6f} ({target_price_change_cents:.2f}¢)"
            )
            logger.info(f"  Порог перестановки: {reposition_threshold_cents:.2f}¢")
            logger.info(f"  Offset (ticks): {offset_ticks}")
            logger.info(f"  Будет переставлен: {'Да' if will_reposition else 'Нет'}")

            # Добавляем ордер в списки для отмены/размещения только если изменение достаточно
            # ВАЖНО: Ордер добавляется в ОБА списка одновременно, чтобы гарантировать:
            # 1. Каждый отмененный ордер имеет соответствующий новый ордер для размещения
            # 2. Списки всегда одинаковой длины (проверяется позже для безопасности)
            # 3. Невозможно отменить ордер без размещения нового (и наоборот)
            if will_reposition:
                # Добавляем ордер в список для отмены
                orders_to_cancel.append(order_id)
                logger.info(
                    f"Ордер {order_id} (Account: {account_id}, Market: {market_id}) добавлен в список для отмены"
                )

                # Подготавливаем параметры нового ордера
                order_side = OrderSide.BUY if side == "BUY" else OrderSide.SELL

                new_order_params = {
                    "old_order_id": order_id,  # Старый order_id для обновления БД
                    "market_id": market_id,
                    "root_market_id": root_market_id,  # Для формирования ссылки на маркет
                    "token_id": token_id,
                    "token_name": token_name,  # Добавляем для уведомлений
                    "side": order_side,
                    "price": new_target_price,
                    "amount": amount,
                    "current_price_at_creation": new_current_price,  # Сохраняем для обновления БД
                    "target_price": new_target_price,  # Сохраняем для обновления БД
                    "account_id": account_id,  # Добавляем для логирования
                    "telegram_id": telegram_id,  # Добавляем для уведомлений
                }

                # Добавляем в список для размещения (всегда в паре с отменой)
                orders_to_place.append(new_order_params)
                logger.info(
                    f"Ордер {order_id} (Account: {account_id}, Market: {market_id}) добавлен в список для размещения"
                )
            else:
                logger.info(
                    f"⏭️ Ордер {order_id} (Account: {account_id}, Market: {market_id}) не будет переставлен: "
                    f"изменение целевой цены недостаточно ({target_price_change_cents:.2f}¢ < {reposition_threshold_cents:.2f}¢)"
                )

            # Добавляем уведомление о смещении цены ТОЛЬКО если ордер будет переставлен
            # Уведомление отправляется только когда изменение достаточно для перестановки
            if will_reposition:
                # Добавляем уведомление о смещении цены только для ордеров, которые будут переставлены
                price_change_notifications.append(
                    {
                        "order_id": order_id,
                        "market_id": market_id,
                        "root_market_id": root_market_id,  # Для формирования ссылки на маркет
                        "token_name": token_name,
                        "side": side,
                        "old_current_price": current_price_at_creation,
                        "new_current_price": new_current_price,
                        "old_target_price": target_price,
                        "new_target_price": new_target_price,
                        "price_change": price_change,
                        "target_price_change": target_price_change,
                        "target_price_change_cents": target_price_change_cents,
                        "reposition_threshold_cents": reposition_threshold_cents,
                        "offset_ticks": offset_ticks,
                        "will_reposition": will_reposition,
                    }
                )
            else:
                logger.info(
                    f"⏭️ Ордер {order_id} не будет переставлен, уведомление не отправляется"
                )

        except Exception as e:
            logger.error(
                f"Ошибка при обработке ордера {db_order.get('order_id', 'unknown')}: {e}"
            )
            # При ошибке не добавляем уведомление, чтобы не вводить пользователя в заблуждение
            continue

    return orders_to_cancel, orders_to_place, price_change_notifications


def cancel_orders_batch(client, order_ids: List[str]) -> List[Dict]:
    """
    Отменяет ордера батчем.

    Args:
        client: Клиент Opinion SDK
        order_ids: Список ID ордеров для отмены

    Returns:
        Список результатов отмены
    """
    try:
        results = client.cancel_orders_batch(order_ids)

        success_count = 0
        failed_count = 0

        for i, result in enumerate(results):
            if result.get("success", False):
                success_count += 1
                # Проверяем, есть ли дополнительная информация в результате
                result_data = result.get("result")
                if result_data:
                    if hasattr(result_data, "errno"):
                        if result_data.errno == 0:
                            logger.info(f"Отменен ордер: {order_ids[i]}")
                        else:
                            logger.error(
                                f"Ошибка при отмене ордера {order_ids[i]}: errno={result_data.errno}, errmsg={getattr(result_data, 'errmsg', 'N/A')}"
                            )
                            failed_count += 1
                            success_count -= 1
                    else:
                        logger.info(f"Отменен ордер: {order_ids[i]}")
                else:
                    logger.info(f"Отменен ордер: {order_ids[i]}")
            else:
                failed_count += 1
                error = result.get("error", "Unknown error")
                logger.error(f"Не удалось отменить ордер {order_ids[i]}: {error}")

        logger.info(f"Отменено ордеров: {success_count}, ошибок: {failed_count}")
        return results

    except Exception as e:
        logger.error(f"Ошибка при batch отмене ордеров: {e}")
        return []


def place_orders_batch(client, orders_params: List[Dict]) -> List:
    """
    Размещает ордера батчем.

    Args:
        client: Клиент Opinion SDK
        orders_params: Список параметров ордеров

    Returns:
        Список результатов размещения
    """
    try:
        client.enable_trading()

        # Преобразуем параметры в PlaceOrderDataInput
        orders = []
        for params in orders_params:
            price_rounded = round(float(params["price"]), 3)

            # makerAmountInQuoteToken может быть int или float, не обязательно str
            amount_value = params["amount"]
            if isinstance(amount_value, str):
                amount_value = float(amount_value)

            order_input = PlaceOrderDataInput(
                marketId=params["market_id"],
                tokenId=params["token_id"],
                side=params["side"],
                orderType=LIMIT_ORDER,
                price=str(price_rounded),
                makerAmountInQuoteToken=amount_value,  # int или float, не str
            )
            orders.append(order_input)

        # Размещаем ордера батчем
        results = client.place_orders_batch(orders, check_approval=False)

        success_count = 0
        failed_count = 0

        for i, result in enumerate(results):
            # Согласно документации: place_orders_batch возвращает List[Any],
            # где каждый элемент имеет структуру: {'success': bool, 'result': API response, 'error': Any}
            # API response содержит: errno (0 = success), errmsg, result (с данными ордера)
            if result.get("success", False):
                # result['result'] - это API response объект с полями errno, errmsg, result
                # result['result'].result - содержит данные ордера (order_data с order_id)
                order_id = "unknown"
                try:
                    result_data = result.get("result")
                    # Согласно документации, API response всегда имеет errno
                    # Проверяем errno == 0 для правильного подсчета успешных размещений
                    if result_data and result_data.errno == 0:
                        order_id = result_data.result.order_data.order_id
                        logger.info(f"Размещен ордер: {order_id}")
                        success_count += 1
                    else:
                        # Если errno != 0, это ошибка, даже если success=True
                        errno = result_data.errno if result_data else "N/A"
                        errmsg = result_data.errmsg if result_data else "No result_data"
                        logger.warning(
                            f"Ошибка размещения ордера {i}: errno={errno}, errmsg={errmsg}"
                        )
                        failed_count += 1
                except (AttributeError, TypeError) as e:
                    logger.error(f"Не удалось извлечь order_id из результата {i}: {e}")
                    failed_count += 1
            else:
                failed_count += 1
                error = result.get("error", "Unknown error")
                logger.error(f"Не удалось разместить ордер {i}: {error}")

        logger.info(f"Размещено ордеров: {success_count}, ошибок: {failed_count}")
        return results

    except Exception as e:
        logger.error(f"Ошибка при batch размещении ордеров: {e}")
        traceback.print_exc()
        return []


async def send_price_change_notification(bot, telegram_id: int, notification: Dict):
    """Отправляет уведомление пользователю о смещении цены."""
    try:
        old_price_cents = notification["old_current_price"] * 100
        new_price_cents = notification["new_current_price"] * 100
        old_target_cents = notification["old_target_price"] * 100
        new_target_cents = notification["new_target_price"] * 100
        price_change_cents = notification["price_change"] * 100

        # Convert offset_ticks to cents
        offset_ticks = notification["offset_ticks"]
        offset_cents = offset_ticks * TICK_SIZE * 100

        # Get reposition information
        target_price_change_cents = notification.get("target_price_change_cents", 0.0)
        reposition_threshold_cents = float(
            notification.get("reposition_threshold_cents")
        )

        side_emoji = (
            """<tg-emoji emoji-id="5258391025281408576">📈</tg-emoji>"""
            if notification["side"] == "BUY"
            else """<tg-emoji emoji-id="5258391025281408576">📉</tg-emoji>"""
        )
        change_sign = "+" if notification["price_change"] > 0 else ""

        # Status message - уведомление отправляется только когда ордер будет переставлен
        status_emoji = "✅"
        status_text = f"Order will be repositioned (change: {target_price_change_cents:.2f} cents &gt;= threshold: {reposition_threshold_cents:.2f} cents)"

        # Формируем ссылку на маркет
        market_id = notification["market_id"]
        root_market_id = notification.get("root_market_id")
        market_url = get_market_url(market_id, root_market_id)

        safe_token = escape(str(notification["token_name"]))
        safe_side = escape(str(notification["side"]))
        message = f"""🔔 <b>Price Change Detected</b>

{side_emoji} <b>{safe_token} {safe_side}</b>
<tg-emoji emoji-id="5258330865674494479">📊</tg-emoji> Market ID: {notification["market_id"]}
🔗 <a href="{market_url}">Market Link</a>

<tg-emoji emoji-id="5258260149037965799">💵</tg-emoji> <b>Current Price:</b>
   Old: {old_price_cents:.2f} cents
   New: {new_price_cents:.2f} cents
   Change: {change_sign}{price_change_cents:.2f} cents

🎯 <b>Target Price:</b>
   Old: {old_target_cents:.2f} cents
   New: {new_target_cents:.2f} cents
   Change: {target_price_change_cents:.2f} cents

⚙️ <b>Settings:</b>
   Offset: {offset_cents:.2f} cents
   Reposition threshold: {reposition_threshold_cents:.2f} cents

{status_emoji} <b>Status:</b> {status_text}"""

        await bot.send_message(chat_id=telegram_id, text=message, parse_mode="HTML")
        logger.info(
            f"Sent price change notification to user {telegram_id} for order {notification['order_id']}"
        )
    except Exception as e:
        logger.error(
            f"Failed to send price change notification to user {telegram_id}: {e}"
        )


async def send_order_updated_notification(
    bot, telegram_id: int, order_params: Dict, new_order_id: str
):
    """Отправляет уведомление пользователю об успешном обновлении ордера в БД."""
    try:
        current_price_cents = order_params["current_price_at_creation"] * 100
        target_price_cents = order_params["target_price"] * 100

        side_emoji = (
            """<tg-emoji emoji-id="5258391025281408576">📈</tg-emoji>"""
            if order_params.get("side") == OrderSide.BUY
            else """<tg-emoji emoji-id="5258391025281408576">📉</tg-emoji>"""
        )
        side_text = "BUY" if order_params.get("side") == OrderSide.BUY else "SELL"

        # Формируем ссылку на маркет
        market_id = order_params["market_id"]
        root_market_id = order_params.get("root_market_id")
        market_url = get_market_url(market_id, root_market_id)

        safe_token = escape(str(order_params.get("token_name", "N/A")))
        safe_order_id = escape(str(new_order_id))
        safe_amount = escape(str(order_params["amount"]))
        message = f"""<b>Order Updated Successfully</b>

{side_emoji} <b>{safe_token} {side_text}</b>
<tg-emoji emoji-id="5258330865674494479">📊</tg-emoji> Market ID: {order_params["market_id"]}
🔗 <a href="{market_url}">Market Link</a>

🆔 <b>New Order ID:</b>
<code>{safe_order_id}</code>

<tg-emoji emoji-id="5258260149037965799">💵</tg-emoji> <b>Current Price:</b> {current_price_cents:.2f} cents
🎯 <b>Target Price:</b> {target_price_cents:.2f} cents
<tg-emoji emoji-id="5258204546391351475">💵</tg-emoji> <b>Amount:</b> {safe_amount} USDT

Order has been successfully moved to maintain the offset."""

        await bot.send_message(chat_id=telegram_id, text=message, parse_mode="HTML")
        logger.info(
            f"Sent order updated notification to user {telegram_id} for order {new_order_id}"
        )
    except Exception as e:
        logger.error(
            f"Failed to send order updated notification to user {telegram_id}: {e}"
        )


async def send_order_placement_error_notification(
    bot,
    telegram_id: int,
    order_params: Dict,
    old_order_id: str,
    errno: int,
    errmsg: str,
):
    """Отправляет уведомление пользователю об ошибке размещения ордера."""
    try:
        # Используем .get() для всех полей с значениями по умолчанию
        current_price = order_params.get("current_price_at_creation", 0.0)
        target_price = order_params.get("target_price", 0.0)
        current_price_cents = current_price * 100
        target_price_cents = target_price * 100

        side_emoji = (
            """<tg-emoji emoji-id="5258391025281408576">📈</tg-emoji>"""
            if order_params.get("side") == OrderSide.BUY
            else """<tg-emoji emoji-id="5258391025281408576">📉</tg-emoji>"""
        )
        side_text = "BUY" if order_params.get("side") == OrderSide.BUY else "SELL"

        # Формируем сообщение об ошибке с информацией из API
        error_type = f"Error {errno}"
        error_description = f"Your order was cancelled, but the new order could not be placed.\n\nError details:\n• Error code: {errno}\n• Error message: {errmsg}"

        message = f"""❌ <b>Order Repositioning Failed</b>

{side_emoji} <b>{order_params.get("token_name", "N/A")} {side_text}</b>
<tg-emoji emoji-id="5258330865674494479">📊</tg-emoji> Market ID: {order_params.get("market_id", "N/A")}

🆔 <b>Cancelled Order ID:</b>
<code>{old_order_id}</code>

<tg-emoji emoji-id="5258260149037965799">💵</tg-emoji> <b>Target Price:</b> {target_price_cents:.2f} cents
<tg-emoji emoji-id="5258204546391351475">💵</tg-emoji> <b>Amount:</b> {order_params.get("amount", "N/A")} USDT

⚠️ <b>{error_type}</b>
{error_description}

<b>⚠️ IMPORTANT:</b> Your old order has been cancelled. Please check your balance and place a new order manually if needed."""

        await bot.send_message(chat_id=telegram_id, text=message)
        logger.info(
            f"Sent order placement error notification to user {telegram_id} for order {old_order_id}"
        )
    except Exception as e:
        logger.error(
            f"Failed to send order placement error notification to user {telegram_id}: {e}"
        )


async def send_order_filled_notification(bot, telegram_id: int, api_order):
    """
    Отправляет предупреждающее уведомление пользователю об исполнении ордера.

    Args:
        bot: Экземпляр aiogram Bot
        telegram_id: ID пользователя в Telegram
        api_order: Объект ордера из API (с полями order_id, market_id, market_title,
                  root_market_id, root_market_title, price, side_enum, outcome,
                  order_amount, filled_amount, и другие)
    """
    try:
        # Извлекаем данные из объекта ордера API
        order_id = getattr(api_order, "order_id", "N/A")
        market_id = getattr(api_order, "market_id", "N/A")
        market_title = getattr(api_order, "market_title", "N/A")
        root_market_id = getattr(api_order, "root_market_id", None)
        root_market_title = getattr(api_order, "root_market_title", "N/A")
        side_enum = getattr(api_order, "side_enum", "N/A")
        outcome = getattr(api_order, "outcome", "N/A")

        # Цена исполнения - используем price из ордера (цена по которой был размещен ордер)
        # Если есть информация о сделках, можно использовать цену из trades
        price_str = getattr(api_order, "price", "0")
        try:
            price_float = float(price_str)
            price_cents = price_float * 100
            price_display = f"{price_cents:.2f}".rstrip("0").rstrip(".")
        except (ValueError, TypeError):
            price_display = str(price_str)

        # Количество
        filled_amount = getattr(api_order, "filled_amount", "0")
        order_amount = getattr(api_order, "order_amount", "0")
        try:
            filled_amount_float = float(filled_amount)
            order_amount_float = float(order_amount)
            amount_display = f"{filled_amount_float:.6f}".rstrip("0").rstrip(".")
        except (ValueError, TypeError):
            amount_display = str(filled_amount)

        # Эмодзи для направления
        side_emoji = (
            """<tg-emoji emoji-id="5258391025281408576">📈</tg-emoji>"""
            if side_enum == "Buy"
            else """<tg-emoji emoji-id="5258391025281408576">📉</tg-emoji>"""
        )

        # Формируем ссылку на корневой маркет
        if root_market_id:
            # Категориальный маркет
            market_url = (
                f"https://app.opinion.trade/detail?topicId={root_market_id}&type=multi"
            )
            market_link_text = (
                root_market_title[:50]
                if root_market_title
                else f"Market {root_market_id}"
            )
        else:
            # Бинарный маркет
            market_url = f"https://app.opinion.trade/detail?topicId={market_id}"
            market_link_text = (
                market_title[:50] if market_title else f"Market {market_id}"
            )

        # Экранируем динамический текст для HTML, чтобы избежать ENTITY_TEXT_INVALID
        safe_market_link_text = escape(market_link_text)
        safe_outcome = escape(str(outcome))
        safe_side_enum = escape(str(side_enum))
        safe_order_id = escape(str(order_id))
        safe_price_display = escape(str(price_display))
        safe_amount_display = escape(str(amount_display))

        message = f"""🚨 <b>Order Filled - Action Required</b>

{side_emoji} <b>{safe_outcome} {safe_side_enum}</b>
<tg-emoji emoji-id="5258330865674494479">📊</tg-emoji> Market ID: {market_id}
<tg-emoji emoji-id="5258503720928288433">📋</tg-emoji> Root Market: <a href="{market_url}">{safe_market_link_text}</a>

🆔 <b>Order ID:</b>
<code>{safe_order_id}</code>

<tg-emoji emoji-id="5258260149037965799">💵</tg-emoji> <b>Filled Price:</b> {safe_price_display}¢
<tg-emoji emoji-id="5258204546391351475">💵</tg-emoji> <b>Filled Amount:</b> {safe_amount_display} USDT

Your order has been successfully filled! Please check the market and consider placing new orders. 🎉"""

        await bot.send_message(chat_id=telegram_id, text=message, parse_mode="HTML")
        logger.info(
            f"Отправлено уведомление об исполнении ордера {order_id} пользователю {telegram_id}"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления пользователю {telegram_id}: {e}")
        logger.error(traceback.format_exc())


async def send_cancellation_error_notification(
    bot, telegram_id: int, failed_orders: List[Dict]
):
    """
    Отправляет уведомление пользователю об ошибке отмены ордеров.

    Args:
        bot: Экземпляр aiogram Bot
        telegram_id: ID пользователя в Telegram
        failed_orders: Список словарей с информацией о неудачных отменах:
            [{"order_id": str, "market_id": int, "token_name": str, "side": str, "errno": int, "errmsg": str}, ...]
    """
    try:
        if not failed_orders:
            return

        # Формируем список неудачных ордеров
        orders_list = []
        for order_info in failed_orders:
            order_id = order_info.get("order_id", "Unknown")
            market_id = order_info.get("market_id", "N/A")
            token_name = order_info.get("token_name", "N/A")
            side = order_info.get("side", "N/A")
            errno = order_info.get("errno", "N/A")
            errmsg = order_info.get("errmsg", "Unknown error")

            orders_list.append(
                f"• Order <code>{order_id}</code>\n"
                f"  Market: {market_id}, Token: {token_name} {side}\n"
                f"  Error: {errno} - {errmsg}"
            )

        orders_text = "\n\n".join(orders_list)

        message = f"""❌ <b>Order Cancellation Failed</b>

⚠️ <b>Failed to cancel {len(failed_orders)} order(s)</b>

The following orders could not be cancelled:
{orders_text}

<b>⚠️ IMPORTANT:</b>
• New orders will NOT be placed (safety check)
• Your old orders remain active
• Please check the orders manually and cancel them if needed
• The repositioning will be retried in the next sync cycle"""

        await bot.send_message(chat_id=telegram_id, text=message)
        logger.info(
            f"Sent cancellation error notification to user {telegram_id} for {len(failed_orders)} failed orders"
        )
    except Exception as e:
        logger.error(
            f"Failed to send cancellation error notification to user {telegram_id}: {e}"
        )


async def async_sync_all_orders(bot, market_id: Optional[int] = None):
    """
    Асинхронная функция синхронизации ордеров с уведомлениями пользователям.

    Args:
        bot: Экземпляр aiogram Bot для отправки уведомлений
        market_id: Фильтр по market_id. Если None, синхронизирует все ордера.
    """
    logger.info("")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 30 + "НАЧАЛО СИНХРОНИЗАЦИИ ОРДЕРОВ" + " " * 30 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("")

    # Получаем все pending ордера с JOIN к аккаунтам
    orders_with_accounts = await get_all_pending_orders_with_accounts(
        market_id=market_id
    )

    logger.info(f"Найдено pending ордеров: {len(orders_with_accounts)}")

    if not orders_with_accounts:
        logger.warning("В базе данных нет pending ордеров")
        return

    # Группируем ордера по account_id
    orders_by_account = {}
    for item in orders_with_accounts:
        account_id = item["account"]["account_id"]
        if account_id not in orders_by_account:
            orders_by_account[account_id] = {
                "account": item["account"],
                "orders": [],
            }
        orders_by_account[account_id]["orders"].append(item["order"])

    logger.info(f"Найдено аккаунтов с pending ордерами: {len(orders_by_account)}")

    # Общая статистика
    total_cancelled = 0
    total_placed = 0
    total_errors = 0

    # Обрабатываем ордера для каждого аккаунта
    for account_id, account_data in orders_by_account.items():
        account = account_data["account"]
        telegram_id = account["telegram_id"]
        proxy_status = account.get("proxy_status", "unknown")

        # Засекаем время начала обработки аккаунта
        account_start_time = time.time()
        account_start_time_str = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(account_start_time)
        )

        logger.info(f"\n{'=' * 80}")
        logger.info(f"Обработка аккаунта {account_id} (пользователь {telegram_id})")
        logger.info(f"Время начала: {account_start_time_str}")
        logger.info(f"Статус прокси: {proxy_status}")
        logger.info(f"{'=' * 80}")

        # Проверяем статус прокси
        # if proxy_status == "failed":
        #     logger.warning(
        #         f"Пропуск аккаунта {account_id}: прокси не работает (статус: failed)"
        #     )
        #     continue

        try:
            # Получаем списки ордеров для отмены и размещения, а также уведомления
            (
                orders_to_cancel,
                orders_to_place,
                price_change_notifications,
            ) = await process_account_orders(
                account_id, account, bot, market_id=market_id
            )

            # Отправляем уведомления о смещении цены (независимо от успешности отмены/создания)
            for notification in price_change_notifications:
                await send_price_change_notification(bot, telegram_id, notification)

            if not orders_to_cancel and not orders_to_place:
                logger.info(f"Нет ордеров для перемещения у аккаунта {account_id}")
                continue

            logger.info(f"Ордеров для отмены: {len(orders_to_cancel)}")
            logger.info(f"Ордеров для размещения: {len(orders_to_place)}")

            # Проверяем, что списки согласованы (должны быть одинаковой длины, если есть ордера для перестановки)
            # Если will_reposition = True, ордер добавляется в ОБА списка одновременно в одном блоке кода,
            # поэтому теоретически несоответствие невозможно. Но эта проверка - защита от багов в логике
            # (например, если в будущем код изменится и ордер будет добавлен только в один список).
            if len(orders_to_cancel) != len(orders_to_place):
                logger.error(
                    f"КРИТИЧЕСКАЯ ОШИБКА: Несоответствие списков! Отмена={len(orders_to_cancel)}, размещение={len(orders_to_place)}"
                )
                logger.error(
                    "Это указывает на ошибку в логике process_account_orders. Пропускаем обработку для безопасности."
                )
                continue

            # Если списки пустые, но есть уведомления - это нормально (изменение недостаточно)
            if not orders_to_cancel:
                logger.info(
                    f"Нет ордеров для перестановки у аккаунта {account_id} (изменение недостаточно для всех ордеров)"
                )
                continue

            # Создаем клиент для аккаунта
            # create_client остается синхронным, но это быстрая операция
            client = create_client(account)

            # Отменяем старые ордера
            cancelled_count = 0
            if orders_to_cancel:
                logger.info(f"🔄 Отмена ордеров для аккаунта {account_id}...")
                # Обертываем синхронный вызов в asyncio.to_thread, чтобы не блокировать event loop
                cancel_results = await asyncio.to_thread(
                    cancel_orders_batch, client, orders_to_cancel
                )

                # Проверяем успешность отмены более тщательно
                # Списки orders_to_cancel и orders_to_place всегда одинаковой длины (проверено выше),
                # поэтому можем безопасно использовать индекс i для обоих списков
                failed_cancellations = []  # Список неудачных отмен для уведомления

                for i, result in enumerate(cancel_results):
                    order_id = orders_to_cancel[i]
                    # Получаем market_id из соответствующего ордера в orders_to_place
                    # Индекс i безопасен, так как списки одинаковой длины
                    market_id_info = f" (Account: {account_id}, Market: {orders_to_place[i].get('market_id', 'N/A')})"
                    is_success = False

                    if result.get("success", False):
                        # Дополнительная проверка через result_data.errno
                        result_data = result.get("result")
                        if result_data and hasattr(result_data, "errno"):
                            if result_data.errno == 0:
                                is_success = True
                                logger.info(
                                    f"Отменен ордер: {order_id}{market_id_info}"
                                )
                            else:
                                # Собираем информацию об ошибке для уведомления
                                errno = result_data.errno
                                errmsg = getattr(result_data, "errmsg", "N/A")
                                logger.error(
                                    f"Ошибка при отмене ордера {order_id}{market_id_info}: errno={errno}, errmsg={errmsg}"
                                )

                                # Сохраняем информацию о неудачной отмене
                                order_params = orders_to_place[i]
                                failed_cancellations.append(
                                    {
                                        "order_id": order_id,
                                        "market_id": order_params.get(
                                            "market_id", "N/A"
                                        ),
                                        "token_name": order_params.get(
                                            "token_name", "N/A"
                                        ),
                                        "side": "BUY"
                                        if order_params.get("side") == OrderSide.BUY
                                        else "SELL",
                                        "errno": errno,
                                        "errmsg": errmsg,
                                    }
                                )
                        else:
                            # Если нет result_data, считаем успешным если success=True
                            is_success = True
                            logger.info(f"Отменен ордер: {order_id}{market_id_info}")
                    else:
                        # Если success=False, собираем информацию об ошибке
                        error = result.get("error", "Unknown error")
                        logger.error(
                            f"❌ Не удалось отменить ордер {order_id}{market_id_info}: {error}"
                        )

                        order_params = orders_to_place[i]
                        failed_cancellations.append(
                            {
                                "order_id": order_id,
                                "market_id": order_params.get("market_id", "N/A"),
                                "token_name": order_params.get("token_name", "N/A"),
                                "side": "BUY"
                                if order_params.get("side") == OrderSide.BUY
                                else "SELL",
                                "errno": "N/A",
                                "errmsg": str(error),
                            }
                        )

                    if is_success:
                        cancelled_count += 1

                total_cancelled += cancelled_count

                # Проверяем, что все ордера успешно отменены
                if cancelled_count != len(orders_to_cancel):
                    failed_count = len(orders_to_cancel) - cancelled_count
                    logger.error(
                        f"Не удалось отменить {failed_count} из {len(orders_to_cancel)} ордеров"
                    )
                    logger.warning(
                        "Пропускаем размещение новых ордеров, так как не все старые были отменены"
                    )

                    # Отправляем уведомление пользователю об ошибке отмены
                    await send_cancellation_error_notification(
                        bot, telegram_id, failed_cancellations
                    )
                    continue

            # Размещаем новые ордера только если все старые успешно отменены
            # БАТЧИ ФОРМИРУЮТСЯ ПО АККАУНТУ: каждый аккаунт обрабатывается отдельно,
            # и для каждого аккаунта создается свой батч ордеров (все ордера одного аккаунта в одном батче)
            if orders_to_place and cancelled_count == len(orders_to_cancel):
                logger.info(f"📝 Размещение ордеров для аккаунта {account_id}...")
                # Обертываем синхронный вызов в asyncio.to_thread, чтобы не блокировать event loop
                place_results = await asyncio.to_thread(
                    place_orders_batch, client, orders_to_place
                )
                # Подсчитываем успешно размещенные ордера для общей статистики
                # Согласно документации: result['success'] = True и result['result'].errno == 0 означает успех
                # (детальное логирование уже происходит в place_orders_batch)
                placed_count = sum(
                    1
                    for r in place_results
                    if isinstance(r, dict)
                    and r.get("success", False)
                    and r.get("result")
                    and r.get("result").errno == 0
                )
                total_placed += placed_count

                # Обновляем цены в БД для успешно размещенных ордеров и отправляем уведомления
                # Также обрабатываем ошибки размещения
                # ВАЖНО: Уведомления об ошибках отправляются для КАЖДОГО ордера отдельно,
                # если его размещение не удалось (не для всего батча целиком)
                # Индекс i в place_results соответствует индексу i в orders_to_place (гарантировано API)
                for i, result in enumerate(place_results):
                    order_params = orders_to_place[
                        i
                    ]  # Берем параметры ордера по индексу
                    old_order_id = order_params.get(
                        "old_order_id"
                    )  # Это order_id старого ордера, который был отменен

                    # Проверяем успешность размещения согласно документации
                    # result['success'] = True и result['result'].errno == 0 означает успех
                    result_data = result.get("result")
                    is_success = (
                        result.get("success", False)
                        and result_data
                        and result_data.errno == 0
                    )

                    if not is_success:
                        # Обрабатываем ошибку размещения для конкретного ордера
                        # Мы знаем какой ордер не разместился: это orders_to_place[i] с old_order_id
                        try:
                            if result_data and result_data.errno != 0:
                                errmsg = result_data.errmsg
                                errno = result_data.errno

                                # Отправляем уведомление пользователю об ошибке для ЭТОГО ордера
                                # В уведомлении будет old_order_id (который был отменен) и информация о новом ордере
                                await send_order_placement_error_notification(
                                    bot,
                                    telegram_id,
                                    order_params,
                                    old_order_id,
                                    errno,
                                    errmsg,
                                )
                                logger.warning(
                                    f"Ошибка размещения ордера {old_order_id} (индекс {i} в батче): errno={errno}, errmsg={errmsg}"
                                )
                            else:
                                # Если нет result_data или success=False
                                error = result.get("error", "Unknown error")
                                logger.error(
                                    f"Не удалось разместить ордер {old_order_id} (индекс {i} в батче): {error}"
                                )
                        except Exception as e:
                            logger.error(
                                f"Ошибка при обработке ошибки размещения ордера {old_order_id}: {e}"
                            )
                        continue

                    # Структура из логов: result['result'].result.order_data.order_id
                    try:
                        result_data = result.get("result")
                        if result_data and result_data.errno == 0:
                            new_order_id = result_data.result.order_data.order_id

                            if new_order_id and old_order_id:
                                # Обновляем ордер в БД
                                await update_order_in_db(
                                    old_order_id,
                                    new_order_id,
                                    order_params["current_price_at_creation"],
                                    order_params["target_price"],
                                )
                                # Отправляем уведомление об успешном обновлении
                                await send_order_updated_notification(
                                    bot, telegram_id, order_params, new_order_id
                                )
                    except (AttributeError, TypeError) as e:
                        logger.error(
                            f"Не удалось извлечь order_id из результата размещения {i}: {e}"
                        )

        except Exception as e:
            logger.error(f"Ошибка при обработке аккаунта {account_id}: {e}")
            total_errors += 1
        finally:
            # Засекаем время окончания обработки аккаунта (всегда выполняется)
            account_end_time = time.time()
            account_end_time_str = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(account_end_time)
            )
            account_elapsed = account_end_time - account_start_time

            logger.info(
                f"⏰ Время окончания обработки аккаунта {account_id}: {account_end_time_str}"
            )
            logger.info(
                f"⏱️  Время обработки аккаунта {account_id}: {account_elapsed:.2f} секунд ({account_elapsed / 60:.2f} минут)"
            )
            logger.info(f"{'=' * 80}")

    # Итоговая статистика
    logger.info("")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 30 + "ИТОГОВАЯ СТАТИСТИКА" + " " * 30 + "║")
    logger.info("╠" + "=" * 78 + "╣")
    logger.info(f"║ Отменено ордеров: {total_cancelled:<63} ║")
    logger.info(f"║ Размещено ордеров: {total_placed:<62} ║")
    logger.info(f"║ Ошибок: {total_errors:<69} ║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("")
