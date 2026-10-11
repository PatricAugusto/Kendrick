import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str


def get_settings() -> Settings:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Token do Telegram não configurado. "
            "Crie um arquivo .env com TELEGRAM_BOT_TOKEN=seu_token."
        )

    return Settings(telegram_bot_token=token)
