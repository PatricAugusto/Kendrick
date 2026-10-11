import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    allowed_user_ids: frozenset[int]


def get_settings() -> Settings:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Token do Telegram não configurado. "
            "Crie um arquivo .env com TELEGRAM_BOT_TOKEN=seu_token."
        )

    raw_allowed_user_ids = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
    if not raw_allowed_user_ids.strip():
        raise RuntimeError(
            "Lista de usuários autorizados não configurada. "
            "Defina TELEGRAM_ALLOWED_USER_IDS no arquivo .env."
        )

    try:
        allowed_user_ids = frozenset(
            int(value.strip()) for value in raw_allowed_user_ids.split(",")
        )
    except ValueError:
        raise RuntimeError(
            "TELEGRAM_ALLOWED_USER_IDS deve conter IDs numéricos separados por vírgula."
        ) from None

    if not allowed_user_ids or any(user_id <= 0 for user_id in allowed_user_ids):
        raise RuntimeError(
            "TELEGRAM_ALLOWED_USER_IDS deve conter IDs positivos separados por vírgula."
        )

    return Settings(
        telegram_bot_token=token,
        allowed_user_ids=allowed_user_ids,
    )
