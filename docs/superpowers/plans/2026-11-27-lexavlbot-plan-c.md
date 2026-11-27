# @lexavlbot Plan C — Max Dialog Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 24/7 client dialogue bot for Max (`@lexav_chat_bot`): receive client messages, generate AI responses from the catalog, notify the owner in Telegram, and auto-send after 5 minutes if the owner does not intervene.

**Architecture:** A background asyncio polling loop fetches updates from Max Bot API for `@lexav_chat_bot`. Each incoming message triggers: catalog + settings load → Haiku 5.5 generates a response → response saved to `client_dialogs` with an `auto_send_at` timestamp → owner notified in Telegram with an [✏️ Переписать] button. The same polling loop checks for expired `auto_send_at` rows and auto-sends them. If the owner taps [✏️ Переписать], the row is cancelled and the owner types a manual reply.

**Tech Stack:** Python 3.12, aiogram 3.17 (Telegram owner notifications), aiosqlite, httpx (Max Bot API REST), openai SDK → OpenRouter (Haiku 5.5 for dialog), asyncio background task.

**Spec:** docs/superpowers/specs/2026-11-27-lexavlbot-spec.md

## Global Constraints

- `DIALOG_MODEL = "anthropic/claude-haiku-5-5"` via OpenRouter — never switch to DeepSeek for dialog
- `price_vip` NEVER sent to AI and NEVER mentioned in responses to clients
- AI catalog input = `get_public_catalog(db)` output (hides price_vip by design)
- Auto-send delay = 300 seconds (5 minutes) — hardcoded, not configurable
- `MAX_DIALOG_BOT_TOKEN` already in `config.py` — do not add it again
- `MANAGER_CONTACT` and `RESPONSE_TIME_HOURS` already in `config.py`
- Max Bot API base: `https://botapi.max.ru`
- Owner notification target: `config.ALLOWED_USER_ID` (Telegram)
- All DB access via `aiosqlite`, no SQLAlchemy
- Tests: pytest + pytest-asyncio, `asyncio_mode=auto`, run from `tg-bot/` directory

## Review Focus

- Client asks for price_vip directly ("дайте оптовую для постоянников") → AI must respond with public wholesale price + @manager, never expose price_vip
- Нестандартный вопрос (not in catalog/settings) → AI must say "уточню у менеджера" + escalate=1, not hallucinate a price
- Max API unavailable during auto-send → `send_message` returns False, row stays unsent, owner gets error notification
- Owner taps [✏️ Переписать] after auto-send already fired → cancelled row ignored gracefully (sent=1 already)
- Bot restarts while dialogs are pending → auto_send_at persisted in DB, polling loop re-reads and fires correctly

---

### Task 10: DB client_dialogs table + CRUD

**Files:**
- Modify: `tg-bot/db/database.py`
- Create: `tg-bot/db/dialogs.py`
- Test: `tg-bot/tests/test_db_dialogs.py`

**Interfaces:**
- Produces:
  - `save_dialog(db, platform, client_id, client_name, message, bot_response, auto_send_at) -> int` — returns new row `id`
  - `get_pending_auto_send(db) -> list[dict]` — rows where `sent=0 AND cancelled=0 AND auto_send_at <= now()`
  - `mark_sent(db, dialog_id) -> None`
  - `cancel_auto_send(db, dialog_id) -> None`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_db_dialogs.py
from datetime import datetime, timedelta, timezone
from db.dialogs import save_dialog, get_pending_auto_send, mark_sent, cancel_auto_send

async def test_save_dialog_returns_id(db):
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    dialog_id = await save_dialog(db, "max", "123", "Иван", "есть икра?", "Да, 3200₽", past)
    assert isinstance(dialog_id, int) and dialog_id > 0

async def test_get_pending_auto_send_returns_expired(db):
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    await save_dialog(db, "max", "123", "Иван", "есть икра?", "Да, 3200₽", past)
    rows = await get_pending_auto_send(db)
    assert len(rows) == 1
    assert rows[0]["client_name"] == "Иван"

async def test_get_pending_auto_send_ignores_future(db):
    future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    await save_dialog(db, "max", "123", "Иван", "есть икра?", "Да, 3200₽", future)
    rows = await get_pending_auto_send(db)
    assert rows == []

async def test_mark_sent_excludes_from_pending(db):
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    dialog_id = await save_dialog(db, "max", "123", "Иван", "?", "Ответ", past)
    await mark_sent(db, dialog_id)
    rows = await get_pending_auto_send(db)
    assert rows == []

async def test_cancel_auto_send_excludes_from_pending(db):
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    dialog_id = await save_dialog(db, "max", "123", "Иван", "?", "Ответ", past)
    await cancel_auto_send(db, dialog_id)
    rows = await get_pending_auto_send(db)
    assert rows == []
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd tg-bot && python -m pytest tests/test_db_dialogs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'db.dialogs'`

- [ ] **Step 3: Add `client_dialogs` to `_SCHEMA` in `db/database.py`**

Add after `style_feedback` table:

```sql
CREATE TABLE IF NOT EXISTS client_dialogs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    platform     TEXT DEFAULT 'max',
    client_id    TEXT,
    client_name  TEXT,
    message      TEXT,
    bot_response TEXT,
    escalated    INTEGER DEFAULT 0,
    sent         INTEGER DEFAULT 0,
    auto_send_at TEXT,
    cancelled    INTEGER DEFAULT 0,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 4: Create `db/dialogs.py`**

Implement the four functions. For `get_pending_auto_send`, use:
```sql
SELECT * FROM client_dialogs
WHERE sent=0 AND cancelled=0 AND auto_send_at <= strftime('%Y-%m-%dT%H:%M:%S', 'now')
```
Return each row as a plain `dict` (use `db.row_factory = aiosqlite.Row`, then `dict(row)`).

- [ ] **Step 5: Run to confirm PASS**

Run: `cd tg-bot && python -m pytest tests/test_db_dialogs.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add tg-bot/db/database.py tg-bot/db/dialogs.py tg-bot/tests/test_db_dialogs.py
git commit -m "feat(dialog): add client_dialogs table and CRUD"
```

---

### Task 11: AI Dialog module

**Files:**
- Create: `tg-bot/ai/prompts/dialog.py`
- Create: `tg-bot/ai/dialog.py`
- Test: `tg-bot/tests/test_dialog_ai.py`

**Interfaces:**
- Consumes: `config.DIALOG_MODEL`, `config.MANAGER_CONTACT`, `config.RESPONSE_TIME_HOURS`
- Produces:
  - `build_dialog_prompt(message: str, catalog: list[dict], settings: dict) -> list[dict]`
    — returns `[{"role": "system", ...}, {"role": "user", ...}]`
    — catalog items must NOT contain `price_vip`
  - `generate_dialog_response(message: str, catalog: list[dict], settings: dict) -> str`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_dialog_ai.py
from unittest.mock import AsyncMock, patch, MagicMock
from ai.prompts.dialog import build_dialog_prompt

CATALOG = [{"name": "Горбуша", "price_retail": 250.0, "price_wholesale": 185.0,
            "origin": "Камчатка", "in_stock": 1, "unit": "кг"}]
SETTINGS = {"delivery_zones": "Москва, СПб", "delivery_min_order": "5 кг"}

def test_build_dialog_prompt_returns_two_messages():
    msgs = build_dialog_prompt("есть икра?", CATALOG, SETTINGS)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"

def test_build_dialog_prompt_has_no_price_vip():
    catalog_with_vip = [{**CATALOG[0], "price_vip": 999.0}]
    msgs = build_dialog_prompt("есть икра?", catalog_with_vip, SETTINGS)
    full_text = str(msgs)
    assert "price_vip" not in full_text
    assert "999" not in full_text

def test_build_dialog_prompt_includes_manager_contact():
    import config
    msgs = build_dialog_prompt("нужна скидка", CATALOG, SETTINGS)
    system = msgs[0]["content"]
    assert config.MANAGER_CONTACT in system

@patch("ai.dialog._client")
async def test_generate_dialog_response_returns_string(mock_client):
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "Да, горбуша есть, 250₽/кг"
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    from ai.dialog import generate_dialog_response
    result = await generate_dialog_response("есть горбуша?", CATALOG, SETTINGS)
    assert isinstance(result, str)
    assert len(result) > 0
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd tg-bot && python -m pytest tests/test_dialog_ai.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `ai/prompts/dialog.py`**

`build_dialog_prompt(message, catalog, settings) -> list[dict]`:
- Strip `price_vip` from each catalog item before building prompt
- System prompt text (from spec §7.2):
  ```
  Ты — помощник продавца морепродуктов. Отвечаешь вежливо и по делу.
  Работаешь СТРОГО по предоставленным данным. Никогда не придумываешь цены,
  условия и наличие.
  Если клиент спрашивает индивидуальную цену — отвечай общим прайсом
  и предлагай обратиться к менеджеру: {MANAGER_CONTACT}.
  Если вопрос не в данных — отвечай "уточню у менеджера и отвечу
  в течение {RESPONSE_TIME_HOURS} ч."
  Каталог (только в наличии): {catalog_json}
  Настройки доставки: {delivery_settings}
  ```
- User message: the client's raw message text

- [ ] **Step 4: Create `ai/dialog.py`**

```python
from openai import AsyncOpenAI
import config
from ai.prompts.dialog import build_dialog_prompt

_client = AsyncOpenAI(api_key=config.OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")

async def generate_dialog_response(message: str, catalog: list[dict], settings: dict) -> str:
    messages = build_dialog_prompt(message, catalog, settings)
    response = await _client.chat.completions.create(
        model=config.DIALOG_MODEL, messages=messages, temperature=0.3, max_tokens=300
    )
    return response.choices[0].message.content.strip()
```

Lower temperature (0.3) for factual dialog vs content generation (0.7).

- [ ] **Step 5: Run to confirm PASS**

Run: `cd tg-bot && python -m pytest tests/test_dialog_ai.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add tg-bot/ai/prompts/dialog.py tg-bot/ai/dialog.py tg-bot/tests/test_dialog_ai.py
git commit -m "feat(dialog): add AI dialog module with Haiku 5.5"
```

---

### Task 12: Max Dialog Platform

**Files:**
- Create: `tg-bot/platforms/max_dialog.py`
- Test: `tg-bot/tests/test_max_dialog_platform.py`

**Interfaces:**
- Consumes: `config.MAX_DIALOG_BOT_TOKEN`
- Produces:
  - `get_updates(offset: int = 0) -> list[dict]` — returns list of update dicts from Max API; returns `[]` on any error
  - `send_message(chat_id: str, text: str) -> bool` — sends a message, returns False on failure

Max Bot API (same base as content bot, different token):
- GET `https://botapi.max.ru/updates?access_token={token}&offset={offset}&limit=100&timeout=5`
- POST `https://botapi.max.ru/messages?access_token={token}` with same payload shape as `max_content.py`

Each update dict from Max API has shape `{"update_id": int, "message": {"body": {"text": str}, "sender": {"user_id": str, "name": str}, "recipient": {"chat_id": str}}}` — parse defensively (use `.get()` everywhere, skip malformed updates).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_max_dialog_platform.py
from unittest.mock import AsyncMock, patch, MagicMock
import pytest

@patch("platforms.max_dialog._get_client")
async def test_get_updates_returns_list_on_success(mock_get_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"updates": [{"update_id": 1, "message": {}}]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_get_client.return_value = mock_client
    from platforms.max_dialog import get_updates
    result = await get_updates(offset=0)
    assert isinstance(result, list)

@patch("platforms.max_dialog._get_client")
async def test_get_updates_returns_empty_on_error(mock_get_client):
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=Exception("network error"))
    mock_get_client.return_value = mock_client
    from platforms.max_dialog import get_updates
    result = await get_updates(offset=0)
    assert result == []

@patch("platforms.max_dialog._get_client")
async def test_send_message_returns_true_on_200(mock_get_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_get_client.return_value = mock_client
    from platforms.max_dialog import send_message
    result = await send_message("chat123", "Привет!")
    assert result is True

@patch("platforms.max_dialog._get_client")
async def test_send_message_returns_false_on_error(mock_get_client):
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=Exception("timeout"))
    mock_get_client.return_value = mock_client
    from platforms.max_dialog import send_message
    result = await send_message("chat123", "Привет!")
    assert result is False
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd tg-bot && python -m pytest tests/test_max_dialog_platform.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `platforms/max_dialog.py`**

```python
import logging
import httpx
import config

logger = logging.getLogger(__name__)
_MAX_API_BASE = "https://botapi.max.ru"

def _get_client() -> httpx.AsyncClient:
    return httpx.AsyncClient()

async def get_updates(offset: int = 0) -> list[dict]:
    url = f"{_MAX_API_BASE}/updates?access_token={config.MAX_DIALOG_BOT_TOKEN}&offset={offset}&limit=100&timeout=5"
    try:
        async with _get_client() as client:
            resp = await client.get(url, timeout=10)
        if resp.status_code != 200:
            logger.error("Max dialog get_updates %s: %s", resp.status_code, resp.text)
            return []
        return resp.json().get("updates", [])
    except Exception as e:
        logger.error("Max dialog get_updates failed: %s", e)
        return []

async def send_message(chat_id: str, text: str) -> bool:
    url = f"{_MAX_API_BASE}/messages?access_token={config.MAX_DIALOG_BOT_TOKEN}"
    payload = {"recipient": {"chat_id": chat_id}, "type": "text", "text": text}
    try:
        async with _get_client() as client:
            resp = await client.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.error("Max dialog send_message %s: %s", resp.status_code, resp.text)
            return False
        return True
    except Exception as e:
        logger.error("Max dialog send_message failed: %s", e)
        return False
```

`_get_client()` as a separate function enables test patching via `@patch("platforms.max_dialog._get_client")`.

- [ ] **Step 4: Run to confirm PASS**

Run: `cd tg-bot && python -m pytest tests/test_max_dialog_platform.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tg-bot/platforms/max_dialog.py tg-bot/tests/test_max_dialog_platform.py
git commit -m "feat(dialog): add Max dialog platform (get_updates, send_message)"
```

---

### Task 13: Owner notification handler

**Files:**
- Create: `tg-bot/handlers/dialog_notification.py`
- Test: `tg-bot/tests/test_dialog_notification.py`

**Interfaces:**
- Consumes: `db/dialogs.py` → `cancel_auto_send`, `mark_sent`; `platforms/max_dialog.py` → `send_message`
- Produces:
  - `async notify_owner(bot, dialog_id: int, client_name: str, question: str, bot_response: str) -> None`
    — sends Telegram message to `ALLOWED_USER_ID` with inline keyboard
  - Callback handler for `F.data.startswith("dialog_rewrite_")` — sets cancelled=1
  - Callback handler for `F.data.startswith("dialog_ok_")` — marks sent=1, fires send_message immediately

The router in `dialog_notification.py` handles ONLY the owner's callbacks, not Max incoming messages (those come from the polling loop).

Keyboard for owner notification:
```
[✏️ Переписать]  [✅ Отправить сейчас]
```
callback_data: `dialog_rewrite_{dialog_id}` / `dialog_ok_{dialog_id}`

After [✏️ Переписать]: owner sees "Напишите ваш вариант ответа:" and can type it.
The FSM state `DialogStates.waiting_manual_reply` stores `pending_dialog_id` and `pending_chat_id`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_dialog_notification.py
from unittest.mock import AsyncMock, MagicMock, patch

async def test_notify_owner_sends_message(bot_mock):
    bot_mock.send_message = AsyncMock()
    from handlers.dialog_notification import notify_owner
    await notify_owner(bot_mock, dialog_id=1, client_name="Иван",
                       question="есть икра?", bot_response="Да, 3200₽/кг")
    bot_mock.send_message.assert_awaited_once()
    call_text = str(bot_mock.send_message.call_args)
    assert "Иван" in call_text
    assert "есть икра?" in call_text

@patch("handlers.dialog_notification.cancel_auto_send", new_callable=AsyncMock)
async def test_rewrite_callback_cancels_auto_send(mock_cancel, bot_mock):
    callback = MagicMock()
    callback.data = "dialog_rewrite_42"
    callback.bot = bot_mock
    callback.message = MagicMock()
    callback.message.answer = AsyncMock()
    callback.message.edit_reply_markup = AsyncMock()
    callback.answer = AsyncMock()
    state = AsyncMock()
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    from handlers.dialog_notification import handle_dialog_rewrite
    await handle_dialog_rewrite(callback, state=state)
    mock_cancel.assert_awaited()

@patch("handlers.dialog_notification.mark_sent", new_callable=AsyncMock)
@patch("handlers.dialog_notification.send_message", new_callable=AsyncMock, return_value=True)
async def test_ok_callback_sends_immediately(mock_send, mock_mark, bot_mock):
    callback = MagicMock()
    callback.data = "dialog_ok_7"
    callback.bot = bot_mock
    callback.message = MagicMock()
    callback.message.edit_reply_markup = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()
    from handlers.dialog_notification import handle_dialog_ok
    # Need dialog row in DB — patch get_dialog
    with patch("handlers.dialog_notification.get_dialog",
               new_callable=AsyncMock,
               return_value={"id": 7, "client_id": "chat_abc", "bot_response": "Да, есть"}):
        await handle_dialog_ok(callback)
    mock_send.assert_awaited_once_with("chat_abc", "Да, есть")
    mock_mark.assert_awaited_once()
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd tg-bot && python -m pytest tests/test_dialog_notification.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Add `get_dialog(db, dialog_id) -> dict | None` to `db/dialogs.py`**

Simple `SELECT * FROM client_dialogs WHERE id=?`, return `dict(row)` or `None`.

Add a test in `test_db_dialogs.py`:
```python
async def test_get_dialog_returns_row(db):
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    dialog_id = await save_dialog(db, "max", "c1", "Иван", "?", "Ответ", past)
    from db.dialogs import get_dialog
    row = await get_dialog(db, dialog_id)
    assert row is not None
    assert row["client_name"] == "Иван"
```

Watch it fail, add `get_dialog` to `db/dialogs.py`, watch it pass.

- [ ] **Step 4: Create `handlers/dialog_notification.py`**

```python
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
import config
from db.database import get_db
from db.dialogs import cancel_auto_send, mark_sent, get_dialog
from platforms.max_dialog import send_message

router = Router()

class DialogStates(StatesGroup):
    waiting_manual_reply = State()

def _notify_keyboard(dialog_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✏️ Переписать", callback_data=f"dialog_rewrite_{dialog_id}"),
        InlineKeyboardButton(text="✅ Отправить сейчас", callback_data=f"dialog_ok_{dialog_id}"),
    ]])

async def notify_owner(bot, dialog_id: int, client_name: str, question: str, bot_response: str) -> None:
    text = (
        f"💬 <b>Новый диалог в Max</b>\n"
        f"Клиент: {client_name}\n"
        f"Вопрос: {question}\n\n"
        f"Ответ бота:\n{bot_response}\n\n"
        f"<i>Автоотправка через 5 мин.</i>"
    )
    await bot.send_message(config.ALLOWED_USER_ID, text, reply_markup=_notify_keyboard(dialog_id), parse_mode="HTML")

@router.callback_query(F.data.startswith("dialog_rewrite_"))
async def handle_dialog_rewrite(callback: CallbackQuery, state: FSMContext) -> None:
    dialog_id = int(callback.data.split("_")[-1])
    async with get_db() as db:
        await cancel_auto_send(db, dialog_id)
        row = await get_dialog(db, dialog_id)
    chat_id = row["client_id"] if row else None
    await state.update_data(pending_dialog_id=dialog_id, pending_chat_id=chat_id)
    await state.set_state(DialogStates.waiting_manual_reply)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Напишите ваш вариант ответа клиенту:")
    await callback.answer()

@router.message(DialogStates.waiting_manual_reply)
async def handle_manual_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    dialog_id = data.get("pending_dialog_id")
    chat_id = data.get("pending_chat_id")
    reply_text = message.text or ""
    if chat_id and reply_text:
        ok = await send_message(chat_id, reply_text)
        if ok:
            async with get_db() as db:
                await mark_sent(db, dialog_id)
            await message.answer("✅ Ответ отправлен клиенту.")
        else:
            await message.answer("⚠️ Не удалось отправить в Max. Попробуйте вручную.")
    await state.clear()

@router.callback_query(F.data.startswith("dialog_ok_"))
async def handle_dialog_ok(callback: CallbackQuery) -> None:
    dialog_id = int(callback.data.split("_")[-1])
    async with get_db() as db:
        row = await get_dialog(db, dialog_id)
        if row and not row["sent"] and not row["cancelled"]:
            ok = await send_message(row["client_id"], row["bot_response"])
            if ok:
                await mark_sent(db, dialog_id)
                await callback.message.answer("✅ Ответ отправлен немедленно.")
            else:
                await callback.message.answer("⚠️ Ошибка отправки в Max.")
        else:
            await callback.message.answer("ℹ️ Уже отправлен или отменён.")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
```

- [ ] **Step 5: Run to confirm PASS**

Run: `cd tg-bot && python -m pytest tests/test_dialog_notification.py tests/test_db_dialogs.py -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add tg-bot/db/dialogs.py tg-bot/handlers/dialog_notification.py \
        tg-bot/tests/test_dialog_notification.py tg-bot/tests/test_db_dialogs.py
git commit -m "feat(dialog): owner notification handler with rewrite FSM and ok callback"
```

---

### Task 14: Polling loop + main.py wiring

**Files:**
- Create: `tg-bot/polling/max_dialog_loop.py`
- Modify: `tg-bot/main.py`
- Test: `tg-bot/tests/test_dialog_loop.py`

**Interfaces:**
- Consumes: `platforms/max_dialog.py`, `ai/dialog.py`, `db/dialogs.py`, `db/catalog.py`, `handlers/dialog_notification.py`
- Produces: `async run_max_dialog_loop(bot) -> None` — infinite loop, to be started as `asyncio.create_task`

Loop logic:
1. `updates = await get_updates(offset)` — fetch new messages
2. For each update: extract `chat_id`, `client_id`, `client_name`, `text` from update dict defensively
3. Load `catalog = await get_public_catalog(db)` and `settings` from settings table
4. `response = await generate_dialog_response(text, catalog, settings)`
5. `auto_send_at = (datetime.now(UTC) + timedelta(seconds=300)).isoformat()`
6. `dialog_id = await save_dialog(db, "max", client_id, client_name, text, response, auto_send_at)`
7. `await notify_owner(bot, dialog_id, client_name, text, response)`
8. Advance offset: `offset = max(u["update_id"] for u in updates) + 1`
9. After processing updates: check `get_pending_auto_send(db)` → for each expired row: `send_message(row["client_id"], row["bot_response"])` → `mark_sent` or log error
10. `await asyncio.sleep(2)` between polling cycles

Error handling: wrap each update in try/except — one bad update must not kill the loop.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_dialog_loop.py
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta, timezone

@patch("polling.max_dialog_loop.get_updates", new_callable=AsyncMock, return_value=[])
@patch("polling.max_dialog_loop.get_pending_auto_send", new_callable=AsyncMock, return_value=[])
async def test_loop_runs_one_cycle_no_updates(mock_pending, mock_updates, bot_mock):
    import asyncio
    from polling.max_dialog_loop import run_one_cycle
    await run_one_cycle(bot_mock, offset=0)
    mock_updates.assert_awaited_once()

@patch("polling.max_dialog_loop.get_updates", new_callable=AsyncMock, return_value=[
    {"update_id": 10, "message": {
        "body": {"text": "есть икра?"},
        "sender": {"user_id": "u123", "name": "Иван"},
        "recipient": {"chat_id": "c456"}
    }}
])
@patch("polling.max_dialog_loop.generate_dialog_response",
       new_callable=AsyncMock, return_value="Да, икра есть, 3200₽/кг")
@patch("polling.max_dialog_loop.get_public_catalog", new_callable=AsyncMock, return_value=[])
@patch("polling.max_dialog_loop.save_dialog", new_callable=AsyncMock, return_value=1)
@patch("polling.max_dialog_loop.notify_owner", new_callable=AsyncMock)
@patch("polling.max_dialog_loop.get_pending_auto_send", new_callable=AsyncMock, return_value=[])
@patch("polling.max_dialog_loop.get_db")
async def test_loop_processes_incoming_message(mock_get_db, mock_pending, mock_notify,
                                               mock_save, mock_catalog, mock_gen,
                                               mock_updates, bot_mock):
    from contextlib import asynccontextmanager
    from unittest.mock import MagicMock
    mock_db = MagicMock()
    @asynccontextmanager
    async def _ctx():
        yield mock_db
    mock_get_db.side_effect = _ctx
    from polling.max_dialog_loop import run_one_cycle
    new_offset = await run_one_cycle(bot_mock, offset=0)
    mock_gen.assert_awaited_once()
    mock_save.assert_awaited_once()
    mock_notify.assert_awaited_once()
    assert new_offset == 11

@patch("polling.max_dialog_loop.get_updates", new_callable=AsyncMock, return_value=[])
@patch("polling.max_dialog_loop.get_pending_auto_send", new_callable=AsyncMock,
       return_value=[{"id": 5, "client_id": "c789", "bot_response": "Да, есть", "sent": 0}])
@patch("polling.max_dialog_loop.send_message", new_callable=AsyncMock, return_value=True)
@patch("polling.max_dialog_loop.mark_sent", new_callable=AsyncMock)
@patch("polling.max_dialog_loop.get_db")
async def test_loop_auto_sends_expired_dialogs(mock_get_db, mock_mark, mock_send,
                                               mock_pending, mock_updates, bot_mock):
    from contextlib import asynccontextmanager
    from unittest.mock import MagicMock
    @asynccontextmanager
    async def _ctx():
        yield MagicMock()
    mock_get_db.side_effect = _ctx
    from polling.max_dialog_loop import run_one_cycle
    await run_one_cycle(bot_mock, offset=0)
    mock_send.assert_awaited_once_with("c789", "Да, есть")
    mock_mark.assert_awaited_once()
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd tg-bot && python -m pytest tests/test_dialog_loop.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'polling'`

- [ ] **Step 3: Create `polling/__init__.py` (empty) and `polling/max_dialog_loop.py`**

Extract `run_one_cycle(bot, offset: int) -> int` as a testable unit:
- Returns the new offset (old offset if no updates)
- Takes all dependencies (get_updates, generate_dialog_response, etc.) as module-level imports that tests can patch
- `run_max_dialog_loop(bot)` = infinite loop calling `run_one_cycle` + `asyncio.sleep(2)`

```python
# polling/max_dialog_loop.py
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from db.catalog import get_public_catalog
from db.database import get_db
from db.dialogs import get_pending_auto_send, mark_sent, save_dialog
from ai.dialog import generate_dialog_response
from handlers.dialog_notification import notify_owner
from platforms.max_dialog import get_updates, send_message

logger = logging.getLogger(__name__)
AUTO_SEND_DELAY_SECONDS = 300

async def run_one_cycle(bot, offset: int) -> int:
    updates = await get_updates(offset)
    for update in updates:
        try:
            msg = update.get("message", {})
            text = msg.get("body", {}).get("text", "").strip()
            sender = msg.get("sender", {})
            recipient = msg.get("recipient", {})
            client_id = str(recipient.get("chat_id", ""))
            client_name = sender.get("name", "Клиент")
            if not text or not client_id:
                continue
            async with get_db() as db:
                catalog = await get_public_catalog(db)
                settings = {}  # TODO: load from settings table in later iteration
            response = await generate_dialog_response(text, catalog, settings)
            auto_send_at = (datetime.now(timezone.utc) + timedelta(seconds=AUTO_SEND_DELAY_SECONDS)).isoformat()
            async with get_db() as db:
                dialog_id = await save_dialog(db, "max", client_id, client_name, text, response, auto_send_at)
            await notify_owner(bot, dialog_id, client_name, text, response)
        except Exception as e:
            logger.error("Dialog loop error on update %s: %s", update.get("update_id"), e)
    if updates:
        offset = max(u["update_id"] for u in updates) + 1
    async with get_db() as db:
        pending = await get_pending_auto_send(db)
    for row in pending:
        try:
            ok = await send_message(row["client_id"], row["bot_response"])
            async with get_db() as db:
                if ok:
                    await mark_sent(db, row["id"])
                else:
                    logger.error("Auto-send failed for dialog %s", row["id"])
        except Exception as e:
            logger.error("Auto-send error for dialog %s: %s", row["id"], e)
    return offset

async def run_max_dialog_loop(bot) -> None:
    offset = 0
    while True:
        offset = await run_one_cycle(bot, offset)
        await asyncio.sleep(2)
```

- [ ] **Step 4: Wire into `main.py`**

Add to `main()`:
```python
from polling.max_dialog_loop import run_max_dialog_loop

async def main() -> None:
    ...existing code...
    # Start Max dialog polling as background task
    asyncio.create_task(run_max_dialog_loop(bot))
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
```

Also add `dialog_notification.router` to dispatcher:
```python
from handlers import catalog, common, content, dialog_notification, kp, price, style
...
dp.include_router(dialog_notification.router)
```

- [ ] **Step 5: Run to confirm PASS**

Run: `cd tg-bot && python -m pytest tests/test_dialog_loop.py -v`
Expected: 3 passed

- [ ] **Step 6: Run full suite**

Run: `cd tg-bot && python -m pytest tests/ -v`
Expected: all pass (44 existing + new tests)

- [ ] **Step 7: Commit**

```bash
git add tg-bot/polling/__init__.py tg-bot/polling/max_dialog_loop.py \
        tg-bot/main.py tg-bot/tests/test_dialog_loop.py
git commit -m "feat(dialog): Max polling loop with auto-send, wire into main"
```

---

## Summary

| Task | Files | Tests |
|------|-------|-------|
| 10 — DB dialogs | `db/database.py`, `db/dialogs.py` | 6 |
| 11 — AI dialog | `ai/prompts/dialog.py`, `ai/dialog.py` | 4 |
| 12 — Max platform | `platforms/max_dialog.py` | 4 |
| 13 — Notification handler | `handlers/dialog_notification.py`, `db/dialogs.py` +1 | 4 |
| 14 — Polling loop | `polling/max_dialog_loop.py`, `main.py` | 3 |
