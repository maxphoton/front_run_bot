"""
Тестовая функция для WebSocket синхронизации.

Отправляет админу информацию о каждом сообщении от WebSocket.
Использует канал market.last.trade для более надежного отслеживания изменений цен.
"""

import asyncio
import json
import logging
from typing import Dict, Optional

import websockets
from aiogram import Bot
from service.config import settings
from service.database import get_all_pending_orders_with_accounts, get_opinion_account

logger = logging.getLogger(__name__)

# WebSocket URL
WS_URL = "wss://ws.opinion.trade"

# Heartbeat interval (30 seconds as per documentation)
HEARTBEAT_INTERVAL = 30.0


class WebSocketTestMonitor:
    """Тестовый монитор WebSocket для отправки информации админу."""

    def __init__(self, bot: Bot):
        """
        Инициализирует тестовый монитор WebSocket.

        Args:
            bot: Экземпляр aiogram Bot для отправки уведомлений
        """
        self.bot = bot
        self.ws_url = WS_URL
        self.admin_api_key: Optional[str] = None
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.running = False
        self.reconnect_delay = 1.0
        self.max_reconnect_delay = 60.0
        self.subscriptions = set()  # Множество подписанных маркетов

    async def _get_admin_api_key(self) -> Optional[str]:
        """
        Получает админский API ключ из настроек или первого аккаунта из БД.

        Returns:
            API ключ или None если не найден
        """
        # Сначала проверяем настройки
        if settings.websocket_api_key:
            return settings.websocket_api_key

        # Если не указан, берем первый аккаунт из БД
        orders_with_accounts = await get_all_pending_orders_with_accounts()
        if orders_with_accounts:
            account = orders_with_accounts[0]["account"]
            account_data = await get_opinion_account(account["account_id"])
            if account_data:
                return account_data.get("api_key")

        logger.warning("Не найден API ключ для WebSocket соединения")
        return None

    async def start(self):
        """Запускает тестовый монитор WebSocket."""
        if self.running:
            logger.warning("Тестовый монитор WebSocket уже запущен")
            return

        self.running = True
        logger.info("Запуск тестового монитора WebSocket")

        # Получаем API ключ
        self.admin_api_key = await self._get_admin_api_key()
        if not self.admin_api_key:
            logger.error(
                "Не удалось получить API ключ для WebSocket. Остановка монитора."
            )
            self.running = False
            return

        # Загружаем активные подписки при старте
        await self._load_active_subscriptions()

        # Запускаем основной цикл
        asyncio.create_task(self._run())

    async def stop(self):
        """Останавливает тестовый монитор WebSocket."""
        logger.info("Остановка тестового монитора WebSocket")
        self.running = False

        # Отменяем heartbeat
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass

        # Закрываем соединение
        if self.ws:
            await self.ws.close()

    async def _load_active_subscriptions(self):
        """Загружает все активные подписки из БД при старте."""
        orders_with_accounts = await get_all_pending_orders_with_accounts()
        subscription_keys = set()

        for item in orders_with_accounts:
            order = item["order"]
            market_id = order.get("market_id")
            root_market_id = order.get("root_market_id")
            # Для categorical markets используем root_market_id, для binary - market_id
            subscription_key = (
                root_market_id if root_market_id is not None else market_id
            )
            if subscription_key:
                subscription_keys.add(subscription_key)

        logger.info(
            f"Загружено {len(subscription_keys)} активных маркетов для подписки"
        )
        self.subscriptions = subscription_keys

    async def _run(self):
        """Основной цикл WebSocket соединения с переподключением."""
        while self.running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"WebSocket соединение закрыто: {e}")
                if self.running:
                    logger.info(
                        f"Переподключение через {self.reconnect_delay:.1f} секунд..."
                    )
                    await asyncio.sleep(self.reconnect_delay)
                    self.reconnect_delay = min(
                        self.reconnect_delay * 2, self.max_reconnect_delay
                    )
            except Exception as e:
                logger.error(f"Ошибка в WebSocket соединении: {e}", exc_info=True)
                if self.running:
                    logger.info(
                        f"Переподключение через {self.reconnect_delay:.1f} секунд..."
                    )
                    await asyncio.sleep(self.reconnect_delay)
                    self.reconnect_delay = min(
                        self.reconnect_delay * 2, self.max_reconnect_delay
                    )

    async def _connect_and_listen(self):
        """Подключается к WebSocket и слушает сообщения."""
        url = f"{self.ws_url}?apikey={self.admin_api_key}"
        logger.info(
            f"Подключение к WebSocket: {url.replace(self.admin_api_key, '***')}"
        )

        try:
            async with websockets.connect(
                url, ping_interval=None, ping_timeout=None
            ) as ws:
                self.ws = ws
                self.reconnect_delay = (
                    1.0  # Сбрасываем задержку при успешном подключении
                )
                logger.info("WebSocket соединение установлено")

                # Запускаем heartbeat
                self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

                # Подписываемся на все активные маркеты
                await self._resubscribe_all()

                # Слушаем сообщения
                async for message in ws:
                    if not self.running:
                        break
                    try:
                        await self._handle_message(message)
                    except Exception as e:
                        logger.error(
                            f"Ошибка при обработке сообщения: {e}", exc_info=True
                        )
        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"Ошибка подключения к WebSocket (неверный статус): {e}")
            raise
        except websockets.exceptions.ConnectionClosedError as e:
            logger.warning(f"WebSocket соединение закрыто с ошибкой: {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка WebSocket соединения: {e}", exc_info=True)
            raise
        finally:
            # Очищаем соединение и heartbeat при разрыве
            self.ws = None
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
                self.heartbeat_task = None

    async def _resubscribe_all(self):
        """Переподписывается на все активные маркеты."""
        orders_with_accounts = await get_all_pending_orders_with_accounts()
        subscriptions_map = {}  # subscription_key -> (market_id, root_market_id)

        for item in orders_with_accounts:
            order = item["order"]
            market_id = order.get("market_id")
            root_market_id = order.get("root_market_id")
            subscription_key = (
                root_market_id if root_market_id is not None else market_id
            )
            if subscription_key:
                subscriptions_map[subscription_key] = (market_id, root_market_id)

        logger.info(f"Переподписка на {len(subscriptions_map)} уникальных маркетов")

        for subscription_key, (market_id, root_market_id) in subscriptions_map.items():
            try:
                await self._send_subscribe(market_id, root_market_id)
                await asyncio.sleep(0.1)  # Небольшая задержка между подписками
            except Exception as e:
                logger.error(f"Ошибка при подписке на маркет {subscription_key}: {e}")

    async def _send_subscribe(
        self, market_id: int, root_market_id: Optional[int] = None
    ):
        """Отправляет сообщение подписки на маркет."""
        if not self.ws:
            return

        try:
            if root_market_id is not None:
                message = {
                    "action": "SUBSCRIBE",
                    "channel": "market.last.trade",
                    "rootMarketId": root_market_id,
                }
            else:
                message = {
                    "action": "SUBSCRIBE",
                    "channel": "market.last.trade",
                    "marketId": market_id,
                }

            await self.ws.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Ошибка при отправке подписки на маркет {market_id}: {e}")

    async def _heartbeat_loop(self):
        """Отправляет heartbeat каждые 30 секунд."""
        while self.running:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                if self.ws:
                    try:
                        await self.ws.send(json.dumps({"action": "HEARTBEAT"}))
                        logger.debug("Heartbeat отправлен")
                    except (
                        websockets.exceptions.ConnectionClosed,
                        websockets.exceptions.ConnectionClosedOK,
                        RuntimeError,
                        AttributeError,
                    ) as e:
                        # Соединение закрыто или недоступно - это нормально
                        logger.debug(f"Heartbeat не отправлен: {type(e).__name__}")
                        break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка при отправке heartbeat: {e}")

    async def _handle_message(self, message: str):
        """Обрабатывает входящее сообщение от WebSocket и отправляет админу."""
        try:
            data = json.loads(message)
            msg_type = data.get("msgType")

            # Пропускаем heartbeat сообщения (ответы на наши heartbeat)
            if (
                msg_type is None
                and data.get("code") == 200
                and data.get("message") == "HEARTBEAT"
            ):
                logger.info("Получен heartbeat ответ, пропускаем")
                return

            if msg_type == "market.last.trade":
                await self._handle_price_update(data)
            else:
                # Отправляем информацию о других типах сообщений
                await self._send_admin_notification(
                    f"📨 Получено сообщение типа: {msg_type}\n\n"
                    f"Данные: {json.dumps(data, indent=2, ensure_ascii=False)}"
                )

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON сообщения: {e}")
            await self._send_admin_notification(
                f"❌ Ошибка парсинга JSON: {e}\n\nСообщение: {message[:200]}"
            )
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения: {e}")
            await self._send_admin_notification(
                f"❌ Ошибка обработки сообщения: {e}\n\nСообщение: {message[:200]}"
            )

    async def _handle_price_update(self, message: Dict):
        """
        Обрабатывает обновление цены из канала market.last.trade и отправляет админу информацию.

        Args:
            message: Сообщение с обновлением цены (содержит side, shares, amount и другие поля)
        """
        market_id = message.get("marketId")
        token_id = message.get("tokenId")
        outcome_side = message.get("outcomeSide")
        price = message.get("price")
        side = message.get("side")  # Buy, Sell, Split, Merge
        shares = message.get("shares")
        amount = message.get("amount")

        if not market_id:
            await self._send_admin_notification(
                "⚠️ Получено обновление цены без marketId\n\n"
                f"Данные: {json.dumps(message, indent=2, ensure_ascii=False)}"
            )
            return

        # Получаем информацию о pending ордерах для этого маркета
        orders_with_accounts = await get_all_pending_orders_with_accounts(
            market_id=market_id
        )
        orders_count = len(orders_with_accounts)

        # Формируем сообщение для админа
        info_message = f"""🔔 <b>WebSocket: Обновление цены (Trade)</b>

<tg-emoji emoji-id="5258330865674494479">📊</tg-emoji> <b>Market ID:</b> {market_id}
🪙 <b>Token ID:</b> {token_id or "N/A"}
<tg-emoji emoji-id="5258391025281408576">📈</tg-emoji> <b>Outcome Side:</b> {outcome_side or "N/A"}
<tg-emoji emoji-id="5258260149037965799">💵</tg-emoji> <b>Price:</b> {price or "N/A"}
📦 <b>Side:</b> {side or "N/A"}
<tg-emoji emoji-id="5258330865674494479">📊</tg-emoji> <b>Shares:</b> {shares or "N/A"}
<tg-emoji emoji-id="5258204546391351475">💵</tg-emoji> <b>Amount:</b> {amount or "N/A"}

<tg-emoji emoji-id="5258503720928288433">📋</tg-emoji> <b>Найдено pending ордеров:</b> {orders_count}

<b>Что будет сделано:</b>
"""

        if orders_count == 0:
            info_message += "• Ордеров для обработки нет\n"
        else:
            # Группируем по аккаунтам
            accounts_count = len(
                set(item["account"]["account_id"] for item in orders_with_accounts)
            )
            info_message += f"• Будет обработано {orders_count} ордеров\n"
            info_message += f"• Для {accounts_count} аккаунт(ов)\n"
            info_message += f"• Будет вызвана функция async_sync_all_orders с market_id={market_id}\n"
            info_message += (
                "• Ордера будут сгруппированы по аккаунтам и обработаны батчами\n"
            )
            info_message += (
                "• Для каждого ордера будет проверена необходимость перестановки\n"
            )

        info_message += f"\n📄 <b>Полное сообщение:</b>\n<code>{json.dumps(message, indent=2, ensure_ascii=False)}</code>"

        await self._send_admin_notification(info_message)

    async def _send_admin_notification(self, message: str):
        """
        Отправляет уведомление админу.

        Args:
            message: Текст сообщения
        """
        if not settings.admin_telegram_id or settings.admin_telegram_id == 0:
            logger.debug("Admin telegram_id не указан, уведомление не отправлено")
            return

        try:
            await self.bot.send_message(
                chat_id=settings.admin_telegram_id, text=message, parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления админу: {e}")
