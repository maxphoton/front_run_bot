# Code Review Checklist

**Scope:** Registration, main menu, account, users, config (recent changes).

---

## Functionality

| Check | Status | Notes |
|-------|--------|--------|
| Code does what it's supposed to do | OK | Invite/no-invite, one_account, main menu, and Portfolio/Help flows behave as intended. |
| Edge cases are handled | OK | New user vs registered, invite valid/invalid, no accounts vs one/many. |
| Error handling is appropriate | Minor | Some `except Exception: pass` (e.g. `message.delete()` in start.py, account.py) swallow errors; acceptable for best-effort delete. |
| No obvious bugs or logic errors | Issue | **Circular import risk:** `account.py` does `from routers.start import ...` and `start.py` does `from routers.account import start_add_account_flow`. If `start` is loaded first, `account` imports `start` while `start` is still loading; `MAIN_MENU_PREFIX` / `build_main_menu_keyboard` may not be defined yet. **Recommendation:** Use a lazy import in `account.py` for `MAIN_MENU_PREFIX` and `build_main_menu_keyboard` (e.g. inside the function that sends the main menu after profile add) to avoid circular import. |

---

## Code Quality

| Check | Status | Notes |
|-------|--------|--------|
| Code is readable and well-structured | OK | Routers and handlers are clear; shared entry points (e.g. `start_check_profile`, `start_add_account_flow`) keep duplication down. |
| Functions are small and focused | OK | Handlers delegate to shared helpers where it makes sense. |
| Variable names are descriptive | OK | `telegram_id`, `invite_code`, `open_orders_count`, etc. |
| No code duplication | OK | Main menu keyboard built in one place; completion/help messages centralized. |
| Follows project conventions | OK | Same router/handler and config patterns as the rest of the bot. |

---

## Security

| Check | Status | Notes |
|-------|--------|--------|
| No obvious security vulnerabilities | OK | No new exposure of secrets or user data. |
| Input validation is present | OK | Invite code format, wallet address, and existing DB checks (e.g. duplicate wallet) are in place. |
| Sensitive data is handled properly | OK | Config from env; credentials go through existing encrypted storage. |
| No hardcoded secrets | OK | `config` uses env; doc URLs and static strings only. |

---

## Recommendations

1. **Circular import (account ↔ start):** In `account.py`, remove the top-level `from routers.start import MAIN_MENU_PREFIX, build_main_menu_keyboard` and import these inside the function that sends the main menu after “Profile added successfully!” (lazy import). This avoids loading `start` while it is still importing `account`.
2. **one_account and remove callback:** When `settings.one_account` is True, `/remove_profile` is no-op, but `process_remove_account` (callback `remove_account_*`) still runs if the user has an old message with that button. For consistency, add `if settings.one_account: return` (and optionally `await callback.answer()`) at the start of `process_remove_account`.
3. **Copy when one_account=True:** `REGISTRATION_COMPLETED_MSG` and `WELCOME_REGISTERED_MSG` still mention “Use /add_profile” and “Use /profile_list”. When `one_account=True` those commands are disabled. Consider shortening or adjusting that text for the one-account case, or leave as-is if the doc link is the main guidance.

---

## Summary

- **Functionality:** OK; one fix recommended (circular import).
- **Code quality:** Good.
- **Security:** No issues found in the reviewed scope.

Apply recommendation 1 (lazy import in `account.py`) to avoid possible import errors; recommendation 2 (ignore remove callback when `one_account`) for consistent behavior.
