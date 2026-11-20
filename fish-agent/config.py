from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    bot_token: str
    owner_telegram_id: int

    # Claude
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-5"

    # PostgreSQL
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "fish_agent"
    postgres_user: str = "fish_agent"
    postgres_password: str

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379

    # Telegram MTProto (for reading groups/channels)
    tg_api_id: int = 0
    tg_api_hash: str = ""
    # Comma-separated list of group usernames, e.g. "rybabaza,moriki_vdk"
    tg_groups: str = ""
    # Path to Telethon session file (without .session extension)
    tg_session_path: str = "tg_reader/session/fish_agent"

    # Schedule
    morning_digest_hour: int = 9
    morning_digest_tz: str = "Asia/Vladivostok"
    parser_interval_minutes: int = 60
    fuzzy_match_threshold: int = 85

    # 2GIS
    twogis_api_key: str = ""

    # SMTP (email outreach)
    smtp_host: str = "sm43.hosting.reg.ru"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "Торговый рыбный дом"

    # IMAP (email inbox reading)
    imap_host: str = "sm43.hosting.reg.ru"
    imap_port: int = 993
    # Uses same smtp_user / smtp_password credentials

    # OpenAI Whisper (voice input)
    openai_api_key: str = ""

    # Telegram channel for auto-posting (e.g. @fish_house_vdk or -1001234567890)
    channel_id: str = ""

    # Postmately MCP server
    postmately_mcp_url: str = "https://api.postmately.com/mcp"
    postmately_api_key: str = ""
    postmately_telegram_channel_id: str = ""

    # Company info for PDF
    company_name: str = "ИП Иванов"
    company_phone: str = ""
    company_telegram: str = ""
    company_email: str = ""
    company_conditions: str = "Минимальный заказ 50 кг."

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    class Config:
        env_file = ".env"


settings = Settings()
