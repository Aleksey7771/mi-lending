import asyncio, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

async def main():
    from telethon import TelegramClient
    from config import settings
    client = TelegramClient(settings.tg_session_path, settings.tg_api_id, settings.tg_api_hash)
    await client.connect()
    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"✅ Авторизован: {me.first_name} (@{me.username})")
    else:
        print("❌ Сессия не авторизована — нужно запустить auth.py")
    await client.disconnect()

asyncio.run(main())
