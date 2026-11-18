# Fish Price Agent — CLAUDE.md

## 1. О проекте
Персональный AI-агент для владельца оптовой торговли рыбой (Дальний Восток). Единственный пользователь — владелец. Интерфейс — Telegram-бот. Автоматизирует: мониторинг цен поставщиков, PDF-прайс/КП, утреннюю сводку в 09:00 VLD, рассылку по email. Полная спецификация: `../specs/2026-11-11-fish-agent.md`.

## 2. Структура проекта
```
fish-agent/
├── bot/
│   ├── main.py            # точка входа aiogram
│   ├── handlers/          # commands.py, text.py, callbacks.py
│   └── middleware.py      # whitelist по user_id
├── agents/
│   ├── orchestrator.py    # Claude Sonnet, intent detection
│   ├── price_agent.py     # сводки, сравнения цен
│   ├── content_agent.py   # посты + КП-текст в стиле владельца
│   ├── pdf_agent.py       # WeasyPrint → PDF
│   ├── outreach_agent.py  # подготовка рассылок
│   └── memory_agent.py    # R/W PostgreSQL-памяти
├── memory/
│   ├── models.py          # SQLAlchemy ORM
│   ├── db.py              # пул соединений PG
│   ├── redis_client.py
│   └── migrations/        # Alembic
├── parsers/
│   ├── fishnet.py         # fishnet.ru
│   ├── fishretail.py      # fishretail.ru
│   ├── fishery.py         # fishery.ru + файлы прайсов
│   └── fuzzy_match.py     # RapidFuzz, threshold=85
├── tg_reader/             # Telethon (V1.5, отдельный контейнер)
│   ├── reader.py
│   └── session/           # авторизация Telethon
├── pdf/
│   ├── generator.py
│   ├── templates/         # preis.html, kp.html
│   └── assets/            # logo.png
├── scheduler/
│   ├── jobs.py            # APScheduler
│   └── tasks/             # morning_digest.py, price_update.py
├── data/                  # suppliers.csv, clients.csv, products.csv
├── style_examples/        # примеры постов (пустые до V2)
├── scripts/
│   ├── import_csv.py      # однократный импорт CSV → PG
│   └── import_style.py    # загрузка style_examples/ → PG
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
└── alembic.ini
```

## 3. Tech Stack

| Компонент | Технология | Фаза |
|-----------|-----------|------|
| Бот | aiogram 3.x | MVP |
| LLM | Claude Sonnet (claude-sonnet-4-5+) | MVP |
| БД долгосрочная | PostgreSQL 16 | MVP |
| Кэш / FSM | Redis 7.x | MVP |
| PDF | WeasyPrint | MVP |
| Fuzzy matching | RapidFuzz | MVP |
| Расписание | APScheduler 3.x | MVP |
| Парсинг веба | httpx + BeautifulSoup4 | MVP |
| Мессенджер владельца | Telethon (User API) | V1.5 |
| Email | SMTP (mail.ru) | V1.5 |
| Голос | Whisper | V2 |
| Контейнеры | Docker Compose | MVP |
| VPS | Hetzner CX22, €4.15/мес | MVP |

## 4. Архитектура

```
Источники цен (фон, каждый час)
  fishnet.ru ──┐
  fishretail.ru─┤──► WebParser ──► PostgreSQL supplier_prices
  fishery.ru ──┘
  TG личные ──────► TgReader  ──► PostgreSQL (V1.5)
  Max личные ──────► MaxReader ──► PostgreSQL (V1.5)
  Ручной ввод ─────► Bot handler ► PostgreSQL

Владелец → Telegram Bot (aiogram)
                │
         Middleware (whitelist user_id)
                │
         Оркестратор (Claude Sonnet)
         intent detection → JSON {intent, params}
         ┌──────┬──────┬──────┬──────┬──────┐
      Price Content PDF Outreach Memory
      Agent  Agent Agent  Agent  Agent
         └──────┴──────┴──────┴──────┴──────┘
                │                    │
           PostgreSQL              Redis
         (долгосрочная)        (кэш/FSM/сессия)

Расписание (APScheduler)
  09:00 VLD → morning_digest → Telegram владельцу
  каждый час → run_parsers   → PostgreSQL
  каждые 5 мин → healthcheck → Telegram если упал
```

## 5. Пять ключевых решений

| Решение | Почему |
|---------|--------|
| **Нет fine-tuning** — обучение через few-shot + 👍/👎 фидбек | Claude API не поддерживает fine-tuning; накопление style_examples в PG дает тот же эффект за 3–4 недели работы |
| **Telethon в V1.5, не MVP** | Главная боль — цены реальных поставщиков из личных чатов. Но авторизация Telethon требует личного аккаунта и первичной настройки с ноутбука — делаем после стабилизации MVP |
| **Рассылка: email авто, TG/WA вручную** | Автоматическая рассылка в Telegram-чаты = бан аккаунта. Email — безопасный канал. Владелец сам жмёт «Переслать» в TG/WA |
| **Единственный пользователь — whitelist user_id** | Нет регистрации, нет ролей. Middleware проверяет один ID из .env. Всем остальным — молчание |
| **APScheduler внутри бота** | Отдельный Celery/n8n — лишний сервис. APScheduler встроен в тот же процесс: меньше инфраструктуры, проще дебаг |

## 6. Тестирование

**Где:** ручные тесты через Telegram + pytest для парсеров и fuzzy match.

**Чек-лист MVP:**
- [ ] `/update треска б/г 182 Иванов` → БД: новая запись, бот подтверждает за ≤30 сек
- [ ] Пересылка сообщения поставщика → LLM парсит → запрос «Это Иванов?»
- [ ] `/preis` → PDF с логотипом за ≤10 сек
- [ ] `/kp Марина` → персональный PDF с ценами за ≤15 сек
- [ ] 09:00 VLD → приходит сводка с изменениями и кнопками
- [ ] `docker stop bot` → через ≤2 мин уведомление в Telegram
- [ ] Чужой user_id → бот молчит, лог пуст
- [ ] `pytest parsers/` → fuzzy: «ТРЕСКА БГ» → «треска б/г» score ≥ 85

## 7. Документация

| Файл | Содержит | Когда обновлять |
|------|---------|----------------|
| `../specs/2026-11-11-fish-agent.md` | Полное ТЗ: БД, промпты, команды, фазы | При изменении архитектуры или добавлении фичи |
| `CLAUDE.md` (этот файл) | Навигация по проекту для Claude | При изменении структуры, стека или ключевых решений |
| `.env.example` | Шаблон переменных окружения | При добавлении нового сервиса/ключа |
| `memory/migrations/` | История схемы БД (Alembic) | При каждом изменении БД |
| `data/*.csv` | Начальные данные поставщиков/клиентов | До первого запуска (Фаза 0) |

## 8. Commands

```bash
# Первый запуск (Фаза 0: данные готовы)
cp .env.example .env              # заполнить все ключи
docker compose up -d postgres redis
python scripts/import_csv.py      # загрузка suppliers/clients/products
alembic upgrade head               # миграции БД

# Запуск MVP
docker compose up -d              # bot + postgres + redis + healthcheck

# Запуск V1.5 (Telethon)
docker compose --profile v1_5 up -d   # + tg_reader

# Перезапуск бота после обновления кода
docker compose build bot && docker compose up -d bot

# Просмотр логов
docker compose logs -f bot
docker compose logs -f tg_reader

# Бэкап БД вручную
docker exec postgres pg_dump -U fish_agent fish_agent | gzip > backup_$(date +%Y%m%d).sql.gz

# Тесты
pytest parsers/ -v
```

## 9. Самообновление

Агент обновляет эти объекты в рантайме (без деплоя):

| Объект | Таблица PG | Команда владельца | Эффект |
|--------|-----------|-------------------|--------|
| Цена поставщика | `supplier_prices` | «обнови треску 182 Иванов» | Следующая сводка использует новую цену |
| Моя цена для клиентов | `my_prices` | «[Обновить мой прайс]» в сводке | Следующий `/preis` и `/kp` с новой ценой |
| Стиль постов | `style_examples` + `agent_memory` | 👍 / 👎 / ✏️ под постом | ContentAgent учитывает при следующей генерации |
| Предпочтения | `agent_memory` | Любая фраза с инструкцией | MemoryAgent сохраняет ключ-значение |
| Расписание сводки | `agent_memory["schedule.*"]` | «Перенеси сводку на 10:00» | APScheduler перепланирует при следующем рестарте |
| Список поставщиков | `suppliers` | «Добавь поставщика: Козлов, Сахалин» | Сразу доступен для `/update` и сравнений |
| Список клиентов | `clients` | «Добавь клиента: Марина, ресторан, Новосибирск» | Сразу доступен для `/kp` и рассылок |

**Стиль-петля (как агент учится):**
```
Генерация поста → 👍 → style_examples (score=1) → следующий промпт
                 → 👎 + «почему» → agent_memory[style.corrections] → промпт
                 → ✏️ исправить → style_examples (is_original=true) → промпт
```
Через 20–30 оцененных постов ContentAgent стабильно пишет в стиле владельца.
