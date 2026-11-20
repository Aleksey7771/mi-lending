"""First-time Telethon session setup.

Run once before starting ad-agent to authorize the MTProto session.
Telegram will ask for phone number + confirmation code.

Usage:
    .venv\\Scripts\\python check_auth.py
"""
import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


async def main() -> None:
    from telethon import TelegramClient
    from config import settings

    os.makedirs(os.path.dirname(settings.tg_session_path) or ".", exist_ok=True)

    client = TelegramClient(
        settings.tg_session_path,
        settings.tg_api_id,
        settings.tg_api_hash,
    )

    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"✅ Уже авторизован: {me.first_name} (@{me.username})")
        await client.disconnect()
        return

    print("📱 Авторизация через Telegram MTProto")
    phone = input("Введи номер телефона (формат +79XXXXXXXXX): ").strip()
    await client.send_code_request(phone)
    code = input("Введи код из Telegram: ").strip()

    try:
        await client.sign_in(phone, code)
    except Exception as exc:
        if "two-steps" in str(exc).lower() or "2fa" in str(exc).lower():
            password = input("Введи пароль двухфакторной авторизации: ").strip()
            await client.sign_in(password=password)
        else:
            raise

    me = await client.get_me()
    print(f"✅ Авторизован как: {me.first_name} (@{me.username})")
    print(f"📁 Сессия сохранена: {settings.tg_session_path}.session")

    # Quick check: list first 3 configured scout groups
    from config import settings as cfg
    print("\n🔍 Проверка доступа к группам из SCOUT_GROUPS:")
    for group in cfg.scout_group_list[:3]:
        try:
            entity = await client.get_entity(group)
            print(f"  ✅ {group} — доступна ({entity.title})")
        except Exception as e:
            print(f"  ❌ {group} — ошибка: {e}")

    await client.disconnect()
    print("\n✅ Готово. Запускай: .venv\\Scripts\\python main.py")


if __name__ == "__main__":
    asyncio.run(main())
