# Code Review Checklist — Front Run Bot

Обзор проекта по чеклисту: функциональность, качество кода, безопасность.

---

## Functionality

| Критерий | Статус | Комментарий |
|----------|--------|-------------|
| Код делает то, что задумано | ✅ | Роутеры market/limit/limit_first, синхронизация ордеров, инвайты, шифрование — соответствуют описанию в README. |
| Обработаны граничные случаи | ⚠️ | В `orders_dialog.py` (строки 90, 398): `float(order.get("reposition_threshold_cents"))` при отсутствии ключа даёт `TypeError` (float(None)). Рекомендация: `float(order.get("reposition_threshold_cents") or 0.5)`. |
| Обработка ошибок уместна | ✅ | В роутерах: `try/except ValueError` для `int()`/`float()` с сообщениями пользователю. В sync_orders и API wrapper — `except Exception` с логированием. |
| Нет очевидных багов | ✅ | Логика BUY/SELL (makerAmountInQuoteToken vs makerAmountInBaseToken), параметризованные SQL-запросы — без явных ошибок. |

---

## Code Quality

| Критерий | Статус | Комментарий |
|----------|--------|-------------|
| Код читаем и структурирован | ✅ | Разделение по `routers/`, `service/`, `opinion/`, понятные имена модулей. |
| Функции небольшие и по одной задаче | ✅ | Хендлеры и вспомогательные функции в целом сфокусированы. |
| Имена переменных описательные | ✅ | `telegram_id`, `account_id`, `reposition_threshold_cents`, `makerAmountInBaseToken` и т.д. |
| Нет дублирования кода | ⚠️ | Повторяющиеся паттерны: выбор аккаунта (int из callback_data + ValueError), ввод amount (float + проверка > 0) в market/limit/limit_first — можно вынести в общие хелперы. Форматирование ордеров в `orders_dialog.py` (строки 84–108 и 392–416) дублируется — стоит вынести в одну функцию. |
| Соблюдены соглашения проекта | ✅ | aiogram 3, FSM, async, type hints, docstrings в ключевых местах. |

---

## Security

| Критерий | Статус | Комментарий |
|----------|--------|-------------|
| Нет очевидных уязвимостей | ✅ | Нет передачи пользовательского ввода в SQL-строки; секреты не логируются. |
| Валидация ввода | ✅ | `api_key` длина и уникальность; `private_key` уникальность; прокси в формате ip:port:login:password; `int()`/`float()` в try/except; проверки amount > 0, цен в диапазоне. |
| Секреты обрабатываются корректно | ✅ | `BOT_TOKEN`, `MASTER_KEY` из env (pydantic-settings). Данные аккаунтов (wallet, private_key, api_key, proxy) шифруются AES-GCM в `service/aes.py`, в БД только cipher+nonce. При логировании WebSocket URL API key маскируется (`url.replace(..., '***')`). |
| Нет захардкоженных секретов | ✅ | Секреты только из `.env`; в коде только константы вроде адресов контрактов и `TICK_SIZE`. |

---

## Дополнительные замечания

1. **SQL-инъекции**: В `database.py` в f-строках подставляются только имена колонок и сформированные `placeholders` ("?", "?,?"); пользовательские данные передаются через `params` — риска инъекций нет.
2. **Исключения**: В основном используется `except Exception as e` с логированием; один раз `except Exception: pass` в `opinion_api_wrapper.py` (около 384) — имеет смысл зафиксировать в комментарии, что пропуск намеренный.
3. **Неиспользуемые переменные** (Ruff): В `sync_orders.py` — `order_amount_float` (L882), `current_price_cents` (L800); можно удалить или использовать.
4. **Роутер floating_order**: В `main.py` не подключается; используется только `calculate_target_price` из `floating_order.py` в `limit_first.py` — структура осознанная, в README отражена.

---

## Итог

- **Functionality**: в целом ок; стоит поправить обработку `reposition_threshold_cents` в `orders_dialog.py`.
- **Code Quality**: ок; при желании уменьшить дублирование в роутерах и в `orders_dialog`.
- **Security**: сильные стороны — шифрование секретов, параметризованные запросы, валидация; замечаний по безопасности нет.

Рекомендуемые следующие шаги:
1. Исправить `float(order.get("reposition_threshold_cents"))` в `orders_dialog.py`.
2. По возможности вынести общую логику ввода amount/account selection в хелперы.
3. Убрать или использовать неиспользуемые переменные в `sync_orders.py`.
