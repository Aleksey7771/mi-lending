from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fish_agent"

    # Telegram Bot
    bot_token: str
    owner_telegram_id: int

    # Telegram MTProto
    tg_api_id: int
    tg_api_hash: str
    tg_session_path: str = "sessions/ad_agent"

    # Claude
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-5"

    # Company
    company_name: str = "Торговый рыбный дом"
    company_phone: str = "+7 914 326 50 50"
    company_email: str = "fish-house@inbox.ru"
    tz: str = "Asia/Vladivostok"

    # Payments
    yukassa_provider_token: str = ""

    # Scout — comma-separated TG group usernames without @
    scout_groups: str = "rybabaza,sebreez,fishretailtrade"

    # Stub API keys (Phase 4)
    avito_api_key: str = ""
    max_api_key: str = ""
    vk_token: str = ""
    instagram_token: str = ""
    tiktok_token: str = ""

    @property
    def scout_group_list(self) -> list[str]:
        return [g.strip() for g in self.scout_groups.split(",") if g.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
