import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    allowed_user_ids: frozenset[int]
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"


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

    ollama_base_url = os.getenv(
        "OLLAMA_BASE_URL",
        "http://localhost:11434",
    ).rstrip("/")
    parsed_ollama_url = urlsplit(ollama_base_url)
    try:
        valid_ollama_url = (
            parsed_ollama_url.scheme in {"http", "https"}
            and bool(parsed_ollama_url.hostname)
            and parsed_ollama_url.port != 0
            and parsed_ollama_url.username is None
            and parsed_ollama_url.password is None
            and not parsed_ollama_url.query
            and not parsed_ollama_url.fragment
        )
    except ValueError:
        valid_ollama_url = False
    if not valid_ollama_url:
        raise RuntimeError(
            "OLLAMA_BASE_URL deve ser uma URL HTTP/HTTPS válida, "
            "como http://localhost:11434."
        )

    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2").strip()
    if not ollama_model:
        raise RuntimeError("OLLAMA_MODEL não pode ficar vazio.")

    return Settings(
        telegram_bot_token=token,
        allowed_user_ids=allowed_user_ids,
        ollama_base_url=ollama_base_url,
        ollama_model=ollama_model,
    )
