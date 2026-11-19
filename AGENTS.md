# Project guide for AI agents

## Repository layout

- Root `index.html` and `fish.html`: static landing page prototypes. `research.md` contains current market and product research; `idea.md` captures the business concept.
- `specs/2026-11-11-fish-agent.md`: Fish Price Agent technical specification.
- `fish-agent/`: Telegram bot and supporting services. `bot/` contains aiogram entry point, handlers, and access whitelist; `agents/` contains orchestration, pricing, content, PDF, outreach, and memory logic; `memory/` contains SQLAlchemy models, PostgreSQL/Redis connections, and Alembic migrations; `parsers/` and `scheduler/` collect prices and run scheduled jobs; `pdf/` contains PDF templates/generation; `scripts/` contains data import and 2GIS tools; `data/` contains supplier, product, and client CSVs.
- `tg_parser/parser.py`: standalone Telethon parser for configured Telegram groups. It filters the latest messages for fish-related price mentions and exports `prices.csv` in the current working directory. It uses `TG_API_ID`, `TG_API_HASH`, and optional `TG_GROUPS`; Telethon creates a local `fish_session.session` authorization file.
- `fish-agent/tg_reader/`: separate Telethon reader for the bot's V1.5 integration.

## Stack

Python 3.11+, aiogram 3, Anthropic API, SQLAlchemy async + asyncpg, PostgreSQL, Redis, Alembic, APScheduler, httpx, BeautifulSoup/lxml, RapidFuzz, Telethon, WeasyPrint, Jinja2, openpyxl, pdfplumber, aiohttp, and pydantic-settings. The landing pages are plain HTML/CSS/JavaScript; there is no Node build setup.

Follow root `CLAUDE.md` for landing-page work and `fish-agent/CLAUDE.md` plus the technical specification for Fish Price Agent work.

## Common commands

Run Fish Price Agent commands from `fish-agent/`.

```powershell
# Local services (requires Docker Compose)
docker compose up -d postgres redis

# Schema and CSV initialization
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe scripts\import_csv.py

# Start the full Compose stack
docker compose up -d

# Basic Python syntax check when changing Python code
.venv\Scripts\python.exe -m compileall -q bot agents memory parsers scheduler scripts tg_reader ..\tg_parser
```

There is no configured linter or checked-in automated test suite at present. The manual MVP checklist is in `fish-agent/CLAUDE.md`; do not claim it passed unless it was run. For the static pages, open `index.html` or `fish.html` in a browser; there is no build command.

## Safety and data handling

- Never read out, expose, overwrite, stage, or commit credentials from `.env` files, Telegram API tokens, `*.session` files, or session journals. `.env.example` may contain placeholders and is safe to track.
- Do not delete, replace, or bulk-transform user data, CSVs, generated PDFs, databases, or Telegram session files without explicit confirmation. Preserve original files when preparing derived data.
- Do not send messages, publish content, or contact customers/providers without explicit authorization.
- Treat `fish-agent/data/` and generated outputs as user data. Inspect only what is needed and avoid printing personal contact details in chat or logs.

## Change workflow

- Before a substantial change, first give a short plan and list the files that will change. For small, self-contained edits, proceed directly.
- After changes, run the relevant validation command above and report exactly what was checked and its result. Do not run database migrations or start services unless the task calls for it.
- Keep changes focused; update project documentation when architecture, commands, or key decisions change.
