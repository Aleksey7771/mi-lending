# @lexavlbot Plan A — Foundation + Catalog

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task.

**Goal:** Рабочий бот с безопасностью, БД, каталогом 50+ позиций и NLU-роутером намерений.

**Architecture:** Расширяем существующий `tg-bot/` — добавляем security middleware, aiosqlite для каталога, Haiku 5.5 для определения намерений. Все handlers регистрируются в существующем `main.py`. После этого плана бот принимает команды каталога голосом и хранит данные.

**Tech Stack:** Python 3.12, aiogram 3.17, aiosqlite, openai SDK → OpenRouter (Haiku 5.5)

**Spec:** `docs/superpowers/specs/2026-11-27-lexavlbot-spec.md`

## Global Constraints

- ALLOWED_USER_ID из `.env` — все неизвестные Telegram ID молча игнорируются
- aiosqlite (не SQLAlchemy) — один пользователь, нет конкурентных записей
- Цены хранятся как REAL (₽/ед), никогда не генерируются AI
- `in_stock` = 0 → позиция не попадает в AI-ответы клиентам
- `price_vip` никогда не возвращается в публичных запросах
- Все токены только из `.env`, не в коде

## Review Focus

- Незарегистрированный пользователь пишет боту → молчание, без ошибки, без логов в чат
- Запрос "обнови горбушу" когда горбуши нет в каталоге → понятная ошибка пользователю
- `price_vip` не должен попасть в `get_public_catalog()` ни при каком запросе
- Две записи с одинаковым `name` → вторая добавляется (не обновляет), нужна защита
- `volume_tiers` как невалидный JSON → не должен ронять запрос к каталогу

---

### Task 1: Инфраструктура — config, security, DB

**Files:**
- Modify: `tg-bot/config.py`
- Modify: `tg-bot/main.py`
- Create: `tg-bot/db/database.py`
- Create: `tg-bot/db/migrations.py`
- Create: `tg-bot/.env.example` (обновить)
- Test: `tg-bot/tests/test_security.py`
- Test: `tg-bot/tests/test_db.py`

**Interfaces:**
- Produces:
  - `config.ALLOWED_USER_ID: int`
  - `config.CONTENT_MODEL: str`, `config.DIALOG_MODEL: str`
  - `db.database.get_db() -> aiosqlite.Connection` (async context manager)
  - `db.database.init_db() -> None` (создаёт таблицы если нет)
  - Middleware `OwnerOnlyMiddleware` зарегистрирован в `dp`

- [ ] **Step 1: Написать тест безопасности**

```python
# tests/test_security.py
async def test_unknown_user_is_ignored(dp, bot):
    """Сообщение от чужого user_id не порождает ответа"""
    update = make_message_update(user_id=99999999, text="hello")
    responses = await dp.feed_update(bot, update)
    assert responses == []

async def test_owner_gets_response(dp, bot):
    """Сообщение от ALLOWED_USER_ID обрабатывается"""
    update = make_message_update(user_id=config.ALLOWED_USER_ID, text="/start")
    responses = await dp.feed_update(bot, update)
    assert len(responses) > 0
```

- [ ] **Step 2: Запустить тест — убедиться что FAIL**

```
pytest tg-bot/tests/test_security.py -v
```

- [ ] **Step 3: Расширить `config.py`**

Добавить: `ALLOWED_USER_ID: int`, `CONTENT_MODEL: str`, `DIALOG_MODEL: str`, `ROUTER_MODEL: str`, `MANAGER_CONTACT: str`, `TELEGRAM_CHANNEL_ID: str`. Поднять ValueError если ALLOWED_USER_ID не задан.

- [ ] **Step 4: Написать `OwnerOnlyMiddleware` в `tg-bot/middleware/owner.py`**

Сигнатура: `async def __call__(self, handler, event: Message, data) -> Any`. Если `event.from_user.id != ALLOWED_USER_ID` — вернуть `None` без вызова handler.

- [ ] **Step 5: Зарегистрировать middleware в `main.py`**

`dp.message.middleware(OwnerOnlyMiddleware())` перед `dp.include_router(...)`.

- [ ] **Step 6: Запустить тест — убедиться что PASS**

```
pytest tg-bot/tests/test_security.py -v
```

- [ ] **Step 7: Написать тест БД**

```python
# tests/test_db.py
async def test_init_db_creates_tables(tmp_path):
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await init_db(db)
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {r[0] for r in await cursor.fetchall()}
    assert {"products", "settings", "style_profile", "style_feedback"} <= tables
```

- [ ] **Step 8: Написать `db/database.py`**

`init_db(db)` создаёт 4 таблицы по схеме из spec §6.3. `get_db()` — async context manager, открывает `lexavlbot.db` из директории бота, включает `PRAGMA foreign_keys = ON` и `row_factory = aiosqlite.Row`.

- [ ] **Step 9: Запустить тест — убедиться что PASS**

```
pytest tg-bot/tests/test_db.py -v
```

- [ ] **Step 10: Обновить `.env.example` и закоммитить**

```bash
git add tg-bot/config.py tg-bot/main.py tg-bot/middleware/ tg-bot/db/ tg-bot/.env.example tg-bot/tests/
git commit -m "feat(bot): add owner middleware, DB init, extended config"
```

---

### Task 2: Каталог товаров — CRUD

**Files:**
- Create: `tg-bot/db/catalog.py`
- Create: `tg-bot/handlers/catalog.py`
- Test: `tg-bot/tests/test_catalog.py`

**Interfaces:**
- Consumes: `db.database.get_db()`
- Produces:
  - `db.catalog.add_product(db, name, category, price_retail, price_wholesale, **kwargs) -> int` (возвращает id)
  - `db.catalog.update_product(db, product_id_or_name: str|int, **fields) -> bool`
  - `db.catalog.get_product(db, name: str) -> dict | None`
  - `db.catalog.get_all_products(db, in_stock_only=False) -> list[dict]`
  - `db.catalog.get_public_catalog(db) -> list[dict]` — без `price_vip`
  - `db.catalog.set_stock(db, name: str, in_stock: bool) -> bool`

- [ ] **Step 1: Написать тесты каталога**

```python
# tests/test_catalog.py
async def test_add_and_get_product(db):
    pid = await add_product(db, name="Горбуша", category="рыба",
                            price_retail=250.0, price_wholesale=185.0,
                            origin="Камчатка")
    product = await get_product(db, "Горбуша")
    assert product["name"] == "Горбуша"
    assert product["price_wholesale"] == 185.0

async def test_public_catalog_hides_vip_price(db):
    await add_product(db, name="Икра", category="икра",
                      price_retail=3200.0, price_wholesale=2900.0,
                      price_vip=2500.0)
    catalog = await get_public_catalog(db)
    item = next(p for p in catalog if p["name"] == "Икра")
    assert "price_vip" not in item or item.get("price_vip") is None

async def test_update_price(db):
    await add_product(db, name="Минтай", category="рыба",
                      price_retail=100.0, price_wholesale=80.0)
    updated = await update_product(db, "Минтай", price_wholesale=85.0)
    assert updated is True
    p = await get_product(db, "Минтай")
    assert p["price_wholesale"] == 85.0

async def test_duplicate_name_raises(db):
    await add_product(db, name="Треска", category="рыба",
                      price_retail=200.0, price_wholesale=160.0)
    with pytest.raises(ValueError, match="уже существует"):
        await add_product(db, name="Треска", category="рыба",
                          price_retail=210.0, price_wholesale=165.0)

async def test_invalid_volume_tiers_json(db):
    # невалидный JSON не должен ронять add_product
    with pytest.raises(ValueError, match="volume_tiers"):
        await add_product(db, name="Кета", category="рыба",
                          price_retail=300.0, price_wholesale=240.0,
                          volume_tiers="not-json")
```

- [ ] **Step 2: Запустить — убедиться что FAIL**

```
pytest tg-bot/tests/test_catalog.py -v
```

- [ ] **Step 3: Написать `db/catalog.py`**

Все функции принимают `db: aiosqlite.Connection`. `add_product` проверяет дубль по `name` (UNIQUE в схеме), валидирует `volume_tiers` через `json.loads`. `get_public_catalog` делает `SELECT` без колонки `price_vip`.

- [ ] **Step 4: Запустить — убедиться что PASS**

```
pytest tg-bot/tests/test_catalog.py -v
```

- [ ] **Step 5: Написать `handlers/catalog.py`**

Обрабатывает свободный текст через NLU (Task 3 роутер ещё не написан — использовать заглушку `intent = "CATALOG_ADD"`). Команды: `/catalog` → список; добавление, обновление, наличие. Показывает таблицу кнопками редактирования через InlineKeyboard.

- [ ] **Step 6: Зарегистрировать router в `main.py`**

`dp.include_router(catalog.router)` после `common.router`.

- [ ] **Step 7: Закоммитить**

```bash
git add tg-bot/db/catalog.py tg-bot/handlers/catalog.py tg-bot/tests/test_catalog.py tg-bot/main.py
git commit -m "feat(catalog): add product CRUD with security and VIP price protection"
```

---

### Task 3: AI Router — определение намерения

**Files:**
- Create: `tg-bot/ai/router.py`
- Create: `tg-bot/ai/prompts/router_prompt.py`
- Test: `tg-bot/tests/test_ai_router.py`

**Interfaces:**
- Consumes: `config.ROUTER_MODEL`, `config.OPENROUTER_API_KEY`
- Produces:
  - `ai.router.detect_intent(text: str) -> str`
  - Возможные значения: `"POST"`, `"KP"`, `"PRICE"`, `"CATALOG_ADD"`, `"CATALOG_UPDATE"`, `"CATALOG_VIEW"`, `"PUBLISH"`, `"STYLE"`, `"OTHER"`

- [ ] **Step 1: Написать тесты роутера (без реального API — мок)**

```python
# tests/test_ai_router.py
@patch("ai.router._llm_classify", return_value="POST")
async def test_post_intent(mock_llm):
    result = await detect_intent("напиши пост про горбушу")
    assert result == "POST"

@patch("ai.router._llm_classify", return_value="CATALOG_ADD")
async def test_catalog_add_intent(mock_llm):
    result = await detect_intent("добавь товар: кета 300р опт")
    assert result == "CATALOG_ADD"

@patch("ai.router._llm_classify", return_value="PRICE")
async def test_price_intent(mock_llm):
    result = await detect_intent("отправь прайс в Max")
    assert result == "PRICE"

@patch("ai.router._llm_classify", return_value="GARBAGE")
async def test_unknown_falls_back_to_other(mock_llm):
    # невалидный ответ LLM → "OTHER"
    result = await detect_intent("фывапролд")
    assert result == "OTHER"
```

- [ ] **Step 2: Запустить — убедиться что FAIL**

```
pytest tg-bot/tests/test_ai_router.py -v
```

- [ ] **Step 3: Написать `ai/prompts/router_prompt.py`**

`ROUTER_SYSTEM_PROMPT: str` — системный промпт из spec §7.3. Список допустимых значений зафиксирован в константе `VALID_INTENTS: set[str]`.

- [ ] **Step 4: Написать `ai/router.py`**

`_llm_classify(text: str) -> str` вызывает OpenRouter с `temperature=0`, `max_tokens=10`. `detect_intent(text)` вызывает `_llm_classify`, если ответ не в `VALID_INTENTS` → возвращает `"OTHER"`. При `APIError` → возвращает `"OTHER"` (не бросает исключение).

- [ ] **Step 5: Запустить — убедиться что PASS**

```
pytest tg-bot/tests/test_ai_router.py -v
```

- [ ] **Step 6: Заменить заглушку в `handlers/catalog.py`**

Убрать `intent = "CATALOG_ADD"` заглушку, подключить `await detect_intent(text)`.

- [ ] **Step 7: Закоммитить**

```bash
git add tg-bot/ai/router.py tg-bot/ai/prompts/router_prompt.py tg-bot/tests/test_ai_router.py tg-bot/handlers/catalog.py
git commit -m "feat(ai): add intent router with Haiku 5.5, wire into catalog handler"
```

---

## Self-Review

**Spec coverage:**
- §5.1 security (ALLOWED_USER_ID) → Task 1 ✅
- §5.2 каталог (50+ позиций, все поля) → Task 2 ✅
- §6.3 schema (5 таблиц) → Task 1 создаёт 4; `client_dialogs` создаётся в Plan C ✅
- §7.3 router prompt → Task 3 ✅
- price_vip защита → Task 2 test ✅
- volume_tiers JSON validation → Task 2 test ✅

**Gaps:**
- `settings` таблица создаётся в Task 1 но команда `/settings` — в Plan B (приемлемо)
- `style_profile` и `style_feedback` создаются в Task 1 но логика — в Plan B (приемлемо)

**Type consistency:** `get_db()` используется в Tasks 2 и 3 с одной и той же сигнатурой ✅

**Proportion:** план описывает интерфейсы и тесты, не реализацию ✅
