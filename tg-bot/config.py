from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

# Owner security — only this Telegram user ID can send commands
_raw_uid = os.getenv("ALLOWED_USER_ID", "")
ALLOWED_USER_ID: int = int(_raw_uid) if _raw_uid.isdigit() else 0

# AI models via OpenRouter
CONTENT_MODEL: str = os.getenv("CONTENT_MODEL", "deepseek/deepseek-chat")
DIALOG_MODEL: str = os.getenv("DIALOG_MODEL", "anthropic/claude-haiku-5-5")
ROUTER_MODEL: str = os.getenv("ROUTER_MODEL", "anthropic/claude-haiku-5-5")

# Publishing
TELEGRAM_CHANNEL_ID: str = os.getenv("TELEGRAM_CHANNEL_ID", "")
MAX_CONTENT_BOT_TOKEN: str = os.getenv("MAX_CONTENT_BOT_TOKEN", "")
MAX_CONTENT_CHANNEL_ID: str = os.getenv("MAX_CONTENT_CHANNEL_ID", "")
MAX_DIALOG_BOT_TOKEN: str = os.getenv("MAX_DIALOG_BOT_TOKEN", "")

# Voice transcription (Groq Whisper — free)
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
WHISPER_MODEL: str = "whisper-large-v3-turbo"

# Business settings
MANAGER_CONTACT: str = os.getenv("MANAGER_CONTACT", "@manager")
RESPONSE_TIME_HOURS: int = int(os.getenv("RESPONSE_TIME_HOURS", "2"))

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не задан в .env")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY не задан в .env")
if not ALLOWED_USER_ID:
    raise ValueError("ALLOWED_USER_ID не задан в .env (нужен целочисленный Telegram ID)")
