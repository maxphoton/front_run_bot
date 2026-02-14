# FrontRun

**First Trading terminal for Opinion in your pocket.**

Telegram bot for [Opinion.trade](https://app.opinion.trade) prediction markets: place and manage orders, keep limit orders at the top of the book, with encrypted credentials and optional invite-based access.

## Features

- **Market orders** – place market orders at current price
- **Limit orders** – place limit orders at a custom price
- **Always-first orders** – keep your limit orders at the top of the order book
- **Portfolio** – check profile (balance, count orders) and open “View all orders” via `/orders`
- **Main menu** – inline buttons for all main actions; main menu is shown after registration, after adding a profile, and on unknown messages (fallback)
- **Help** – short doc link and a “Main menu” button (link preview disabled)

### 🔐 Registration and accounts
- **Registration modes** (env `INVITE_REQUIRED`):
  - `true`: `/start` asks for a 10-character invite code, then completion message with main menu; use `/add_profile` to add your Opinion profile
  - `false`: `/start` registers the user and immediately starts the add-profile flow (wallet, private key, API key)
- **One account mode** (env `ONE_ACCOUNT`, default `true`): when enabled, the bot does not react to `/add_profile`, `/profile_list`, or `/remove_profile`; only one Opinion profile per user (added via `/start` when invite is disabled)
- **Multiple accounts** (when `ONE_ACCOUNT=false`): add/list/remove profiles via `/add_profile`, `/profile_list`, `/remove_profile`
- **Encrypted storage**: wallet, private key, API key encrypted with AES-GCM; async SQLite (`aiosqlite`), no plaintext secrets
- **Validation**: unique wallet/private key/API key per account; API connection tested before saving; atomic invite use when invite is required

### 🎫 Invite Management (Admin Only)
- **Invite Generation**: Admin command `/get_invites` generates and displays 10 unused invite codes
- **Automatic Creation**: System automatically creates new invites if fewer than 10 are available
- **Statistics**: View total, used, and unused invite counts
- **One-Time Use**: Each invite can only be used once
- **Unique Codes**: 10-character alphanumeric codes with uniqueness validation

### 👤 Account Management
- **Add Account**: `/add_profile` to add a new Opinion profile (wallet, private key, API key). When `ONE_ACCOUNT=true`, this command is disabled
- **List Accounts**: `/profile_list` to view all your Opinion profiles (disabled when `ONE_ACCOUNT=true`)
- **Remove Account**: `/remove_profile` to delete an Opinion profile (disabled when `ONE_ACCOUNT=true`)
- **Check Account / Portfolio**: Main menu “Portfolio” or `/check_profile` – profile statistics (balance, count orders, positions) and the line “You may see all orders by command '/orders'”
- **Multiple Accounts**: When `ONE_ACCOUNT=false`, multiple Opinion profiles per user; when placing orders you select which account to use

### 👥 User Management (Admin Only)
- **User Deletion**: Admin command `/delete_user` allows removing users from the database
- **Complete Removal**: Deletes user, all their accounts, orders, and clears associated invites
- **Statistics**: Admin command `/stats` to view database statistics
- **Re-registration Support**: Deleted users can register again with a new invite code

### 📊 Market Order Placement
- **Interactive Flow**: Step-by-step process for placing limit orders
- **Market Analysis**: View market information including:
  - Best bid/ask prices for YES and NO tokens
  - Spread and liquidity metrics
  - Top 5 bids and asks with price visualization in cents
- **Smart Validation**: Automatic balance checks and price validation
- **Categorical Markets**: Support for multi-outcome markets with submarket selection
- **Reposition Threshold**: Configurable threshold (in cents) for when orders should be repositioned
- **Error Handling**: Clear error messages when API calls fail

### 💰 Order Management
- **Order List**: View all your orders with pagination (`/orders` command)
- **Order Search**: Search orders by order ID, market ID, market title, token name, or side
- **Order Cancellation**: Cancel orders directly from the bot interface with detailed error messages
- **Price Offset in Cents**: Set order prices relative to best bid using intuitive cent-based offsets
- **Direction Selection**: Choose BUY (below current price) or SELL (above current price, can be used to sell shares)
- **Order Confirmation**: Review all settings before placing orders
- **Order Status Tracking**: View order status (pending, finished, canceled)
- **Bot-Only Orders**: Only orders created through the bot can be managed; manually placed orders are not displayed
- **Execution Notifications**: Automatic notifications when orders are executed with execution details

### 🔄 Automatic Order Synchronization
- **Current Implementation**: Periodic synchronization via REST API every 60 seconds
- **Order Status Monitoring**: Checks order status via API before processing
  - Automatically updates database when orders are filled or cancelled externally
  - Sends notifications for filled orders with order details (price, market link)
  - Silently updates cancelled orders without notifications
- **Price Tracking**: Monitors market price changes and maintains constant offset from current price
- **Smart Updates**: Only moves orders when price change exceeds configurable threshold (default 0.5 cents)
- **Batch Operations**: Efficiently cancels and places orders in batches per user
- **User Notifications**: Sends notifications about:
  - Price changes (before repositioning)
  - Order updates (after successful repositioning)
  - Order filled (when order is executed)
  - Placement errors (with detailed error messages)
- **Non-blocking**: All operations are asynchronous and don't block the bot's event loop
- **Safety Checks**: Only places new orders after successfully canceling old ones

### 🚀 Upcoming: WebSocket-Based Synchronization
- **Planned Migration**: The bot will soon transition to real-time WebSocket-based order synchronization
- **Benefits**: 
  - **Real-time Updates**: Instant price change detection via WebSocket subscriptions to `market.last.trade` channel
  - **Reduced Latency**: Orders will be repositioned immediately when prices change, instead of waiting up to 60 seconds
  - **Lower API Load**: WebSocket connections reduce the number of REST API calls needed for price monitoring
  - **Debounced Processing**: Price updates are debounced (3 seconds) to group frequent changes and reduce unnecessary repositioning
  - **Automatic Reconnection**: Robust reconnection logic with exponential backoff for connection stability
- **Implementation Status**: WebSocket synchronization module (`websocket_sync.py`) is implemented and ready for activation
- **Backward Compatibility**: The new WebSocket system will use the same order synchronization logic, ensuring consistent behavior

### 📝 Logging & Monitoring
- **Separate Log Files**: Different log files for different modules:
  - `logs/bot.log` - Main bot operations (INFO level and above)
  - `logs/sync_orders.log` - Order synchronization operations
- **Dual-Level Logging**: 
  - File logs: INFO+ with detailed format including `filename:lineno` for debugging
  - Console logs: WARNING+ with simplified format for important messages only
- **Detailed Logging**: Comprehensive logging with user IDs, account IDs, market IDs, and execution times
- **Performance Monitoring**: Logs start time, end time, and duration for each account's processing
- **Error Tracking**: Full traceback logging for debugging

### 💬 Support System
- **User Support**: Command `/support` allows users to contact the administrator
- **Message Forwarding**: Support messages (text or photo with caption) are forwarded to the admin
- **User Information**: Admin receives user ID, username, and name with each support message
- **No Registration Required**: Support command is available to all users (no registration needed)
- **Confirmation**: Users receive confirmation when their message is sent

### 📖 Help & Documentation
- **Help**: `/help` shows a short message with a link to the documentation (link preview disabled)
- **Main menu button**: Help and Profile Statistics messages include an inline “Main menu” button to open the main menu with all actions

### 🛡️ Security & Performance
- **Anti-Spam Protection**: Built-in middleware to prevent message spam
- **Async Architecture**: Fully asynchronous codebase using `aiosqlite` and `asyncio`
- **Non-blocking I/O**: All database and API operations are non-blocking
- **Modular Design**: Clean separation of concerns with routers and modules
- **Registration Check**: Commands verify user registration before execution

## Getting Started

### Prerequisites

- Python 3.13+
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Opinion Labs API Key (obtain from [the form](https://docs.google.com/forms/d/1h7gp8UffZeXzYQ-lv4jcou9PoRNOqMAQhyW4IwZDnII/viewform?edit_requested=true))
- BNB Chain RPC URL
- Wallet address and private key for Opinion.trade
- Admin Telegram ID (for invite management)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd trade_bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root:
```env
BOT_TOKEN=your_telegram_bot_token
MASTER_KEY=your_32_byte_hex_encryption_key
RPC_URL=your_bnb_chain_rpc_url
ADMIN_TELEGRAM_ID=your_telegram_user_id
```

4. Generate a master key for encryption:
```python
import secrets
print(secrets.token_hex(32))
```

5. Run the bot:
```bash
cd bot
python main.py
```

Or using Docker (if Dockerfile is configured):
```bash
docker-compose up -d
```

## Usage

### Registration

**When `INVITE_REQUIRED=true` (default in .env.example):**
1. `/start` → enter your 10-character invite code → registration complete; main menu is shown
2. Use `/add_profile` to add your Opinion profile (unless `ONE_ACCOUNT=true`, in which case add profile only via the flow started by `/start` when invite is disabled)

**When `INVITE_REQUIRED=false`:**
1. `/start` → you are registered immediately and the add-profile flow starts (wallet, private key, API key)
2. After adding the profile, the main menu is shown

**Add profile (when allowed):** Enter Balance spot address from [Opinion.trade profile](https://app.opinion.trade?code=BJea79), private key, API key (and proxy if needed). Data is encrypted; wallet/private key/API key must be unique; API connection is tested before saving.

💡 **Note**: When `ONE_ACCOUNT=false`, you can add multiple Opinion profiles via `/add_profile`. When `ONE_ACCOUNT=true`, add/profile_list/remove commands are disabled.

### Invite Management (Admin Only)

1. Use `/get_invites` to get 10 unused invite codes
2. The system automatically creates new invites if needed
3. View statistics: total, used, and unused invite counts
4. Share invite codes with users who need access

### Managing Accounts

When `ONE_ACCOUNT=false`: use `/add_profile`, `/profile_list`, `/remove_profile` to add, list, or remove Opinion profiles. When `ONE_ACCOUNT=true`, these commands are disabled.

**Check profile (Portfolio):** Main menu “Portfolio” or `/check_profile` – USDT balance, count orders, positions; message ends with “You may see all orders by command '/orders'”. Response includes a “Main menu” button.

### Placing Orders

Use the **main menu** (inline buttons after `/start` or on any unknown message) or commands:

- **Market order**: Main menu “Market order” or `/market` – place a market order at current price
- **Limit order**: Main menu “Limit order” or `/limit` – place a limit order at a custom price
- **Always-first order**: Main menu “Always-first order” or `/limit_first` – place a limit order that stays at the top of the order book

Flow (for any order type): select account (if multiple), enter market URL from Opinion.trade, for categorical markets select submarket, review market info, enter amount, side (YES/NO), direction (BUY/SELL), confirm and place.

### Managing Orders

1. Use `/orders` to view all your orders
2. Browse orders with pagination (10 orders per page)
3. Use the search function to find specific orders
4. Cancel orders by entering the order ID (order list remains visible for easy copying)
5. View order details: status (pending/finished/canceled), price, amount, market, creation date

⚠️ **Note**: You can only manage orders that were created through the bot. Orders placed manually on the platform are not displayed.

📬 **Notifications**: When an order is executed, the bot automatically sends you a notification with execution details (price, market link, etc.).

### Getting Help

- `/help` or main menu “Help”: short message with a link to the documentation and an inline “Main menu” button to return to the main menu

### Contacting Support

1. Use `/support` to contact the administrator
2. Enter your question or describe the issue
3. You can send text or a photo with a caption
4. Your message will be forwarded to the administrator with your user information (ID, username, name)
5. You'll receive a confirmation when your message is sent

## Project Structure

```
bot/
├── main.py                  # Main bot entry point, background tasks
├── help_text.py             # Multi-language help text (English, Russian, Chinese)
├── routers/                 # Bot command routers
│   ├── start.py             # Registration (/start), main menu keyboard
│   ├── account.py           # Account management (/add_profile, /profile_list, /remove_profile; disabled when ONE_ACCOUNT)
│   ├── market.py            # Market order (/market)
│   ├── limit.py             # Limit order (/limit)
│   ├── limit_first.py       # Always-first order (/limit_first)
│   ├── orders.py            # Orders management router (/orders command)
│   ├── orders_dialog.py     # Order management dialog (aiogram-dialog)
│   ├── users.py             # User commands (/help, /support, /check_profile)
│   ├── admin.py             # Admin commands (/get_db, /get_invites, /delete_user, /stats)
│   └── invites.py           # Invite management functions
├── service/                 # Core services
│   ├── config.py            # Configuration and settings management
│   ├── database.py          # Async database operations (aiosqlite)
│   ├── aes.py               # AES-GCM encryption utilities
│   ├── logger_config.py     # Logging configuration and setup
│   └── proxy_checker.py     # Proxy health checking
├── opinion/                 # Opinion.trade integration
│   ├── client_factory.py    # Opinion SDK client creation and proxy setup
│   ├── opinion_api_wrapper.py  # Opinion API wrapper functions (async)
│   ├── sync_orders.py       # Automatic order synchronization background task (REST API)
│   └── websocket_sync.py    # WebSocket-based real-time order synchronization (planned)
├── middlewares/             # Bot middlewares
│   ├── spam_protection.py   # Anti-spam middleware
│   └── typing_middleware.py # Typing indicator middleware
├── logs/                    # Log files directory
│   ├── bot.log              # Main bot operations log
│   └── sync_orders.log      # Order synchronization log
└── users.db                 # SQLite database (created automatically)
```

## Architecture

The bot uses a modular router-based architecture:

- **Routers**: Separate routers for different features in `routers/`
  - `start.py` - Registration, main menu keyboard
  - `account.py` - Account management (add/list/remove profile; disabled when ONE_ACCOUNT)
  - `market.py`, `limit.py`, `limit_first.py` - Order placement
  - `orders.py` / `orders_dialog.py` - Order management
  - `users.py` - Help, support, check_profile (Portfolio)
  - `admin.py` - Admin commands
  - `plug.py` - Fallback: show main menu on unknown messages
- **Services**: Core services in `service/` directory
  - `config.py` - Configuration management
  - `database.py` - Database operations
  - `aes.py` - Encryption utilities
- **Opinion Integration**: Opinion.trade integration in `opinion/` directory
  - `client_factory.py` - SDK client creation
  - `opinion_api_wrapper.py` - API wrapper functions
  - `sync_orders.py` - Order synchronization (current: REST API polling)
  - `websocket_sync.py` - WebSocket-based real-time synchronization (planned)
- **Async Database**: All database operations use `aiosqlite` for non-blocking I/O
- **Background Tasks**: 
  - Order synchronization runs every 60 seconds (REST API polling)
  - WebSocket synchronization (planned) will provide real-time updates instead of periodic polling
- **Dialogs**: Complex multi-step interactions use `aiogram-dialog` for better UX
- **Middleware**: 
  - Global anti-spam protection for all messages and callbacks
  - Typing indicator middleware for better UX
- **API Wrapper**: Centralized async wrapper for Opinion API calls

## Security

- **AES-GCM Encryption**: Industry-standard encryption for sensitive data
- **Local Storage**: All data stored locally on your server
- **No Third-Party Sharing**: Your credentials are never shared with third parties
- **Encrypted Database**: SQLite database contains only encrypted data
- **Async Operations**: Non-blocking I/O prevents performance issues
- **Invite System**: Access control through invite codes

## Configuration

Environment variables (see `.env.example`):

- `BOT_TOKEN`: Telegram bot token (required)
- `MASTER_KEY`: 32-byte hex key for encryption (required)
- `RPC_URL`: BNB Chain RPC endpoint (required)
- `ADMIN_TELEGRAM_ID`: Telegram user ID for admin commands (optional; 0 = disabled)
- `INVITE_REQUIRED`: `true` = registration requires invite code; `false` = open registration, `/start` starts add-profile flow
- `ONE_ACCOUNT`: `true` = one Opinion profile per user; `/add_profile`, `/profile_list`, `/remove_profile` are disabled; `false` = multiple profiles allowed
- `WEBSOCKET_API_KEY`: Opinion Labs API key for WebSocket (optional)
- `PROXY`: Global proxy (optional). Per-account proxy can be set when adding a profile (when `ONE_ACCOUNT=false`).

## Commands

### User Commands
- `/start` - Register (with invite if `INVITE_REQUIRED=true`) or open main menu if already registered
- `/add_profile` - Add an Opinion profile (disabled when `ONE_ACCOUNT=true`)
- `/profile_list` - List Opinion profiles (disabled when `ONE_ACCOUNT=true`)
- `/remove_profile` - Remove an Opinion profile (disabled when `ONE_ACCOUNT=true`)
- `/check_profile` - Profile statistics (balance, count orders, positions); “Portfolio” in main menu does the same
- `/market` - Place a market order (also via main menu)
- `/limit` - Place a limit order (also via main menu)
- `/limit_first` - Place an always-first limit order (also via main menu)
- `/orders` - View, search, and manage orders
- `/help` - Short doc link and “Main menu” button
- `/support` - Contact administrator (text or photos)

### Admin Commands
- `/get_db` - Export user database and logs as ZIP archive (admin only)
- `/get_invites` - Get 10 unused invite codes with statistics (admin only)
- `/delete_user` - Delete a user from the database (admin only)
- `/stats` - View database statistics (admin only)

## Automatic Order Synchronization

### Current Implementation (REST API Polling)

The bot currently synchronizes your orders every 60 seconds using REST API polling:

### How it works:
1. **Order Retrieval**: Retrieves all pending orders with account information from the database
2. **Account Grouping**: Groups orders by account_id for efficient processing
3. **Account Processing**: For each account:
   - **Client Creation**: Creates Opinion SDK client for the account
   - **Status Check**: For each pending order, checks status via API
     - If order is finished: updates database to 'finished', sends notification with order details (price, market link)
     - If order is canceled: updates database to 'canceled', skips processing silently (no notification)
     - If status check fails: continues with normal processing (graceful degradation)
   - **Price Monitoring**: Monitors market prices and maintains a constant offset (in ticks) between the current market price and your order's target price
   - **Smart Updates**: Only moves orders when the price change exceeds the reposition threshold (default 0.5 cents)
   - **Batch Operations**: Efficiently cancels and places orders in batches per account
   - **Database Updates**: Updates database only for successfully placed orders
   - **Notifications**: Sends notifications for important events

4. **Notifications**: You'll receive notifications when:
   - Market price changes and orders need to be moved (before repositioning, only if order will be repositioned)
   - Orders are successfully updated with new prices (after repositioning)
   - Orders are filled (with order details and market link)
   - Cancellation errors occur (with detailed error messages)
   - Placement errors occur (with detailed error messages)

### Features:
- **Efficiency**: Skips repositioning when change < threshold (saves API calls and gas fees)
- **Reliability**: Only places new orders after successfully canceling old ones
- **Safety**: Validates all operations via API response codes (errno == 0)
- **User Awareness**: Detailed notifications for all important events
- **Performance**: Logs execution time for each account's processing
- **Account Isolation**: Each account is processed independently with its own API client

### Planned: WebSocket-Based Real-Time Synchronization

The bot will soon transition to WebSocket-based synchronization for real-time order updates:

- **Real-Time Price Updates**: Subscribes to `market.last.trade` WebSocket channel for instant price change notifications
- **Immediate Repositioning**: Orders are repositioned immediately when prices change, eliminating the 60-second polling delay
- **Debounced Processing**: Price updates are debounced (3 seconds) to group frequent changes and reduce unnecessary API calls
- **Automatic Market Subscription**: Automatically subscribes to all markets with active orders on startup
- **Dynamic Subscription Management**: Automatically subscribes/unsubscribes when orders are created/cancelled
- **Robust Reconnection**: Automatic reconnection with exponential backoff (1s to 60s) for connection stability
- **Heartbeat Support**: Sends heartbeat messages every 30 seconds to keep connection alive
- **Same Core Logic**: Uses the same proven order synchronization logic from `sync_orders.py` for consistency

## Dependencies

- `aiogram==3.23.0` - Telegram Bot API framework
- `aiogram-dialog==2.4.0` - Dialog system for complex interactions
- `aiosqlite==0.22.0` - Async SQLite driver for non-blocking database operations
- `opinion-clob-sdk==0.4.3` - Opinion.trade SDK for market interactions
- `cryptography==46.0.3` - AES-GCM encryption
- `pydantic==2.12.5` - Settings management
- `pydantic-settings==2.12.0` - Environment variable settings
- `python-dotenv==1.2.1` - Environment variable loading
- `httpx==0.28.1` - HTTP client for proxy checking
- `websockets==14.0` - WebSocket client for real-time order synchronization (planned)
- `pytest==9.0.2` - Testing framework (development)
- `pytest-asyncio==1.3.0` - Async test support (development)

## Technical Details

### Async Architecture
- All database operations use `aiosqlite` for true async I/O
- API calls are wrapped in `asyncio.to_thread()` to prevent blocking
- Background tasks run independently without blocking the main event loop:
  - Order synchronization: runs every 60 seconds (REST API polling, current implementation)
  - WebSocket synchronization: real-time updates via WebSocket subscriptions (planned)
- Opinion API wrapper provides async interface for synchronous SDK
- All routers and handlers are fully async

### Order Synchronization Algorithm
1. Retrieves all pending orders with account information from the database
2. Groups orders by account_id
3. For each account:
   - Skips accounts with `failed` proxy status
   - Creates Opinion SDK client for the account
   - Gets active orders from the database for this account
   - For each order:
     - **Status Check**: Checks order status via API
       - If filled: updates DB, sends notification, skips processing
       - If cancelled: updates DB, skips processing
       - If status check fails: continues with normal processing (graceful degradation)
     - Fetches current market price (best_bid for BUY, best_ask for SELL)
     - Calculates new target price using saved `offset_ticks`
     - Calculates price change in cents
     - If price change ≥ `reposition_threshold_cents`, adds to cancellation/placement lists
     - Sends price change notification (only if order will be repositioned)
   - Cancels old orders in batch (validates via errno == 0)
   - Places new orders in batch (only if all old orders were cancelled)
   - Updates database with new order parameters (only for successful placements)
   - Sends order update notification (for successful placements)
   - Sends error notification (for failed placements)
4. Logs statistics: total cancelled, placed, errors

### Invite System
- Invites are stored in `invites` table with fields: id, invite (unique), telegram_id, created_at, used_at
- Invite codes are 10-character alphanumeric strings
- Invites are validated before registration and used atomically at the end
- Admin can generate invites via `/get_invites` command
- System automatically creates new invites if needed

### Database Schema
- **users**: Basic user information
  - `telegram_id` (PRIMARY KEY): User's Telegram ID
  - `username`: Telegram username
  - `created_at`: Registration timestamp
- **opinion_accounts**: Encrypted Opinion profile credentials
  - `account_id` (PRIMARY KEY): Auto-increment account ID
  - `telegram_id` (FOREIGN KEY): Reference to users table
  - `wallet_address_cipher`, `wallet_nonce`: Encrypted wallet address
  - `private_key_cipher`, `private_key_nonce`: Encrypted private key
  - `api_key_cipher`, `api_key_nonce`: Encrypted API key
  - `proxy_cipher`, `proxy_nonce`: Encrypted proxy (required for each account)
  - `proxy_status`: Proxy health status (`active`, `failed`, `unknown`)
  - `proxy_last_check`: Last proxy health check timestamp
  - All sensitive data encrypted with AES-GCM
  - Unique constraints on wallet address, private key, and API key per account
- **orders**: Order information
  - `id` (PRIMARY KEY): Auto-increment order ID
  - `account_id` (FOREIGN KEY): Reference to opinion_accounts table
  - `order_id`: Opinion.trade order ID
  - `market_id`, `market_title`: Market information
  - `token_id`, `token_name`: Token information (YES/NO)
  - `side`: Order side (BUY/SELL)
  - `current_price`, `target_price`: Price information
  - `offset_ticks`, `offset_cents`: Price offset
  - `amount`: Order amount in USDT
  - `status`: Order status (`pending`, `finished`, `canceled`)
  - `reposition_threshold_cents`: Minimum price change to trigger repositioning
  - `created_at`: Order creation timestamp
- **invites**: Invite codes and usage tracking
  - `id` (PRIMARY KEY): Auto-increment invite ID
  - `invite` (UNIQUE): 10-character alphanumeric invite code
  - `telegram_id`: User who used the invite (NULL if unused)
  - `created_at`: Invite creation timestamp
  - `used_at`: Invite usage timestamp (NULL if unused)

## Disclaimer

This bot is provided as-is for educational and personal use. Always ensure you understand the risks involved in trading on prediction markets. The developers are not responsible for any financial losses.

## Testing

The project includes comprehensive tests for the order synchronization module. See [tests/README.md](tests/README.md) for detailed information about:
- Test structure and coverage
- How to run tests
- Test configuration
- Covered test cases

## Support

For issues, questions, or contributions, please open an issue on GitHub.
