"""
Текст инструкции для команды /help.
"""

HELP_TEXT = """📖 <b>Инструкция по работе с ботом</b>

<b>🎯 Цель бота:</b>
Бот автоматически поддерживает лимитные ордера, не давая им исполниться. Когда текущая цена приближается к цене ордера, бот автоматически переставляет ордер на безопасное расстояние. Синхронизация происходит каждые 60 секунд.

<b>🔐 Регистрация:</b>
<b>Шаг 1:</b> Команда <b>/start</b>
• При первом запуске введите инвайт-код
• После успешной регистрации вы получите доступ к боту

<b>Шаг 2:</b> Команда <b>/add_profile</b>
📹 <a href="https://t.me/cmchn_public/165">Видео гайд по добавлению аккаунта</a>
• Добавьте аккаунт Opinion для работы с ордерами
• При добавлении аккаунта укажите:
  • <b>Кошелек</b> — тот, для которого получен API ключ
  • <b>Приватный ключ</b> — от того же кошелька
  • <b>API ключ</b> — полученный для этого кошелька

⚠️ <b>Важно:</b> Все три параметра (кошелек, приватный ключ, API ключ) должны относиться к одному кошельку. API ключ от другого кошелька не позволит размещать ордера.

💡 <b>Множественные аккаунты:</b> Вы можете добавить несколько аккаунтов Opinion к одному Telegram аккаунту. При размещении ордера вы сможете выбрать, какой аккаунт использовать.

<b><tg-emoji emoji-id="5258011929993026890">👤</tg-emoji> Управление аккаунтами:</b>
• <b>/add_profile</b> — добавить новый аккаунт Opinion
• <b>/profile_list</b> — просмотреть все ваши аккаунты
• <b>/remove_profile</b> — удалить аккаунт
• <b>/check_profile</b> — проверить баланс, ордера и позиции аккаунта. При вызове команды автоматически проверяется

<b><tg-emoji emoji-id="5258330865674494479">📊</tg-emoji> Размещение ордера (/floating_order):</b>
1. <b>Выберите аккаунт</b> — если у вас несколько аккаунтов
2. Введите ссылку на маркет <a href="https://app.opinion.trade?code=BJea79">Opinion.trade</a>
3. Если маркет категориальный — выберите подмаркет
4. Просмотрите информацию о маркете (спред, ликвидность, лучшие цены)
5. Введите сумму в USDT (например: 10)
6. Выберите сторону: ✅ YES или ❌ NO
7. Просмотрите топ-5 бидов и асков
8. Укажите смещение цены в центах (например: 0.1)
   Это расстояние от лучшей цены покупки (best bid), на котором будет размещен ордер
9. Выберите направление: <tg-emoji emoji-id="5258391025281408576">📈</tg-emoji> BUY или 📉 SELL
   (SELL можно использовать для продажи shares)
10. Укажите порог изменения цены в центах (например: 0.5)
    Это минимальное изменение цены, при котором бот переставит ордер
11. Подтвердите и разместите ордер

<b>Пример:</b>
Маркет: "Будет ли дождь завтра?"
Сумма: 10 USDT
Сторона: YES
Смещение: 0.1 цента
Направление: BUY
Порог изменения: 0.5 цента

Ордер будет размещен на 0.1 цента ниже текущей лучшей цены покупки. Бот будет автоматически переставлять ордер, когда цена изменится на 0.5 цента или более.

<b><tg-emoji emoji-id="5258503720928288433">📋</tg-emoji> Просмотр ордеров (/orders):</b>
Команда позволяет:
• Просмотреть все ваши ордера (сгруппированы по аккаунтам)
• Отменить ордер
• Найти ордер по ID, market ID, названию маркета, токену или стороне
• Просмотреть статус ордера (pending/finished/canceled)

⚠️ <b>Важно:</b> Управлять можно только ордерами, которые были созданы через бота. Ордера, размещенные вручную на платформе, не отображаются.

<b>🔄 Автоматическая синхронизация:</b>
Бот автоматически синхронизирует ваши ордера каждые 60 секунд:
• Проверяет статус ордеров через API
• Отслеживает изменения цены рынка
• Переставляет ордера при достаточном изменении цены
• Отправляет уведомления о важных событиях

<b>📬 Уведомления:</b>
Бот отправляет уведомления о:
• Изменении цены и перестановке ордера (перед перестановкой)
• Успешном обновлении ордера (после перестановки)
• Исполнении ордера (с деталями и ссылкой на маркет)
• Ошибках отмены или размещения ордера

<b>💬 Поддержка:</b>
По всем вопросам обращайтесь через команду <b>/support</b>
Вы можете отправить текстовое сообщение или фото с подписью.

<b>📚 Документация:</b> <a href="https://opinionbot.gitbook.io/documentation/">opinionbot.gitbook.io/documentation</a>"""

HELP_TEXT_ENG = """📖 <b>Bot Usage Instructions</b>

<b>🎯 Bot Purpose:</b>
The bot automatically maintains limit orders, preventing them from being executed. When the current price approaches the order price, the bot automatically repositions the order to a safe distance. Synchronization occurs every 60 seconds.

<b>🔐 Registration:</b>
<b>Step 1:</b> Command <b>/start</b>
• On first launch, enter the invite code
• After successful registration, you'll get access to the bot

<b>Step 2:</b> Command <b>/add_profile</b>
📹 <a href="https://t.me/cmchn_public/165">Video guide on adding an profile</a>
• Add an Opinion profile to work with orders
• When adding an profile, specify:
  • <b>Wallet</b> — the one for which the API key was obtained
  • <b>Private key</b> — from the same wallet
  • <b>API key</b> — obtained for this wallet

⚠️ <b>Important:</b> All three parameters (wallet, private key, API key) must belong to the same wallet. An API key from another wallet will not allow placing orders.

💡 <b>Multiple Profiles:</b> You can add multiple Opinion profiles to one Telegram profile. Each profile can have its own proxy. When placing an order, you'll be able to select which profile to use.

<b><tg-emoji emoji-id="5258011929993026890">👤</tg-emoji> Profile Management:</b>
• <b>/add_profile</b> — add a new Opinion profile
• <b>/profile_list</b> — view all your profiles
• <b>/remove_profile</b> — remove an profile
• <b>/check_profile</b> — check profile balance, orders, and positions. When called, it automatically checks and updates the profile's proxy status

<b><tg-emoji emoji-id="5258330865674494479">📊</tg-emoji> Placing an Order (/floating_order):</b>
1. <b>Select Profile</b> — if you have multiple profiles
2. Enter the <a href="https://app.opinion.trade?code=BJea79">Opinion.trade</a> market link
3. If the market is categorical — select a submarket
4. Review market information (spread, liquidity, best prices)
5. Enter the amount in USDT (e.g., 10)
6. Select side: ✅ YES or ❌ NO
7. View top 5 bids and asks
8. Specify price offset in cents (e.g., 0.1)
   This is the distance from the best bid price where the order will be placed
9. Select direction: <tg-emoji emoji-id="5258391025281408576">📈</tg-emoji> BUY or 📉 SELL
   (SELL can be used to sell shares)
10. Specify price change threshold in cents (e.g., 0.5)
    This is the minimum price change at which the bot will reposition the order
11. Confirm and place the order

<b>Example:</b>
Market: "Will it rain tomorrow?"
Amount: 10 USDT
Side: YES
Offset: 0.1 cents
Direction: BUY
Change threshold: 0.5 cents

The order will be placed 0.1 cents below the current best bid price. The bot will automatically reposition the order when the price changes by 0.5 cents or more.

<b><tg-emoji emoji-id="5258503720928288433">📋</tg-emoji> Viewing Orders (/orders):</b>
The command allows you to:
• View all your orders (grouped by profiles)
• Cancel an order
• Find an order by ID, market ID, market title, token name, or side
• View order status (pending/finished/canceled)

⚠️ <b>Important:</b> You can only manage orders that were created through the bot. Orders placed manually on the platform are not displayed.

<b>🔄 Automatic Synchronization:</b>
The bot automatically synchronizes your orders every 60 seconds:
• Checks order status via API
• Monitors market price changes
• Repositions orders when price change is sufficient
• Sends notifications about important events

<b>📬 Notifications:</b>
The bot sends notifications about:
• Price changes and order repositioning (before repositioning)
• Successful order updates (after repositioning)
• Order execution (with details and market link)
• Cancellation or placement errors

<b>💬 Support:</b>
For all questions, contact us via the <b>/support</b> command
You can send a text message or a photo with a caption.

<b>📚 Docs:</b> <a href="https://opinionbot.gitbook.io/documentation/">opinionbot.gitbook.io/documentation</a>"""

HELP_TEXT_CN = """📖 <b>机器人使用说明</b>

<b>🎯 机器人目的:</b>
机器人自动维护限价订单，防止订单被执行。当当前价格接近订单价格时，机器人会自动将订单重新定位到安全距离。同步每60秒进行一次。

<b>🔐 注册:</b>
<b>步骤1:</b> 命令 <b>/start</b>
• 首次启动时，输入邀请码
• 注册成功后，您将获得对机器人的访问权限

<b>步骤2:</b> 命令 <b>/add_profile</b>
📹 <a href="https://t.me/cmchn_public/165">添加账户视频指南</a>
• 添加Opinion账户以处理订单
• 添加账户时，请指定：
  • <b>钱包</b> — 获取API密钥的钱包
  • <b>私钥</b> — 来自同一钱包
  • <b>API密钥</b> — 为此钱包获取的

⚠️ <b>重要:</b> 所有三个参数（钱包、私钥、API密钥）必须属于同一个钱包。来自其他钱包的API密钥将无法下订单。

💡 <b>多个账户:</b> 您可以将多个Opinion账户添加到一个Telegram账户。每个账户可以有自己的代理。下订单时，您可以选择使用哪个账户。

<b><tg-emoji emoji-id="5258011929993026890">👤</tg-emoji> 账户管理:</b>
• <b>/add_profile</b> — 添加新的Opinion账户
• <b>/profile_list</b> — 查看所有账户
• <b>/remove_profile</b> — 删除账户
• <b>/check_profile</b> — 检查账户余额、订单和持仓。调用时自动检查并更新账户的代理状态

<b><tg-emoji emoji-id="5258330865674494479">📊</tg-emoji> 下订单 (/floating_order):</b>
1. <b>选择账户</b> — 如果您有多个账户
2. 输入 <a href="https://app.opinion.trade?code=BJea79">Opinion.trade</a> 市场链接
3. 如果市场是分类市场 — 选择子市场
4. 查看市场信息（价差、流动性、最佳价格）
5. 输入USDT金额（例如：10）
6. 选择方向：✅ YES 或 ❌ NO
7. 查看前5个买入价和卖出价
8. 指定价格偏移（以美分计，例如：0.1）
   这是订单将放置的最佳买入价（best bid）的距离
9. 选择方向：<tg-emoji emoji-id="5258391025281408576">📈</tg-emoji> BUY 或 📉 SELL
   （SELL可用于出售shares）
10. 指定价格变化阈值（以美分计，例如：0.5）
    这是机器人将重新定位订单的最小价格变化
11. 确认并下订单

<b>示例:</b>
市场："明天会下雨吗？"
金额：10 USDT
方向：YES
偏移：0.1美分
方向：BUY
变化阈值：0.5美分

订单将放置在当前最佳买入价下方0.1美分处。当价格变化0.5美分或更多时，机器人将自动重新定位订单。

<b><tg-emoji emoji-id="5258503720928288433">📋</tg-emoji> 查看订单 (/orders):</b>
该命令允许您：
• 查看所有订单（按账户分组）
• 取消订单
• 通过ID、市场ID、市场名称、代币名称或方向查找订单
• 查看订单状态（pending/finished/canceled）

⚠️ <b>重要:</b> 您只能管理通过机器人创建的订单。在平台上手动放置的订单不会显示。

<b>🔄 自动同步:</b>
机器人每60秒自动同步您的订单：
• 通过API检查订单状态
• 监控市场价格变化
• 当价格变化足够时重新定位订单
• 发送重要事件的通知

<b>📬 通知:</b>
机器人发送关于以下内容的通知：
• 价格变化和订单重新定位（重新定位前）
• 成功的订单更新（重新定位后）
• 订单执行（包含详情和市场链接）
• 取消或下单错误

<b>💬 支持:</b>
如有任何问题，请通过 <b>/support</b> 命令联系我们
您可以发送文本消息或带说明的照片。

<b>📚 文档:</b> <a href="https://opinionbot.gitbook.io/documentation/">opinionbot.gitbook.io/documentation</a>"""
