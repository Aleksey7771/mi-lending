"""Shared aiogram Bot singleton — import from here, not from main.py."""
from aiogram import Bot
from config import settings

bot: Bot = Bot(token=settings.bot_token)
