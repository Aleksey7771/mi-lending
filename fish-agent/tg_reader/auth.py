r"""
Одноразовая авторизация Telethon.
Запустить ОДИН РАЗ из папки fish-agent:

    .\.venv\Scripts\python.exe tg_reader/auth.py

После успешного входа появится файл tg_reader/session/fish_agent.session
Больше этот скрипт запускать не нужно — сессия сохранена.
"""

import asyncio
import os
import sys

# Добавляем корень проекта в PYTHONPATH
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


async def main() -> None:
    try:
        from telethon import TelegramClient
        from telethon.errors import SessionPasswordNeededError
    except ImportError:
        print("❌  Установи telethon: .venv\\Scripts\\pip install telethon>=1.36.0")
        return

    from config import settings

    if not settings.tg_api_id or not settings.tg_api_hash:
        print("❌  Заполни TG_API_ID и TG_API_HASH в .env")
        print("    Получить на: https://my.telegram.org → API development tools")
        return

    session_path = settings.tg_session_path
    os.makedirs(os.path.dirname(session_path), exist_ok=True)

    print(f"🔑  API_ID: {settings.tg_api_id}")
    print(f"📁  Сессия будет сохранена в: {session_path}.session")
    print()

    client = TelegramClient(session_path, settings.tg_api_id, settings.tg_api_hash)

    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"✅  Уже авторизован как: {me.first_name} (@{me.username})")
        await client.disconnect()
        return

    phone = input("📱  Введи номер телефона (формат +79001234567): ").strip()
    await client.send_code_request(phone)

    code = input("📨  Введи код из Telegram: ").strip()

    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        password = input("🔐  Введи пароль двухфакторной аутентификации: ").strip()
        await client.sign_in(password=password)

    me = await client.get_me()
    print(f"\n✅  Авторизован как: {me.first_name} (@{me.username})")
    print(f"💾  Сессия сохранена в: {session_path}.session")
    print("\n🚀  Теперь можно запускать бота — TG парсер будет работать автоматически.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
