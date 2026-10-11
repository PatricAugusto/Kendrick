import pytest

from kendrick_bot.config import Settings, get_settings


def test_get_settings_reads_telegram_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kendrick_bot.config.load_dotenv", lambda: None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "123, 456")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    assert get_settings() == Settings(
        telegram_bot_token="test-token",
        allowed_user_ids=frozenset({123, 456}),
    )


def test_get_settings_reads_ollama_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("kendrick_bot.config.load_dotenv", lambda: None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "123")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:3b")

    assert get_settings() == Settings(
        telegram_bot_token="test-token",
        allowed_user_ids=frozenset({123}),
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5:3b",
    )


def test_get_settings_rejects_empty_ollama_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("kendrick_bot.config.load_dotenv", lambda: None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "123")
    monkeypatch.setenv("OLLAMA_MODEL", "  ")

    with pytest.raises(RuntimeError, match="OLLAMA_MODEL"):
        get_settings()


@pytest.mark.parametrize(
    "url",
    ["", "ftp://localhost:11434", "http://user:pass@localhost:11434", "http://"],
)
def test_get_settings_rejects_invalid_ollama_urls(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
) -> None:
    monkeypatch.setattr("kendrick_bot.config.load_dotenv", lambda: None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "123")
    monkeypatch.setenv("OLLAMA_BASE_URL", url)

    with pytest.raises(RuntimeError, match="OLLAMA_BASE_URL"):
        get_settings()


def test_get_settings_fails_when_telegram_token_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("kendrick_bot.config.load_dotenv", lambda: None)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "123")

    with pytest.raises(RuntimeError, match="Token do Telegram não configurado"):
        get_settings()


@pytest.mark.parametrize("raw_ids", ["", "abc", "12,abc", "0", "-123", "12,"])
def test_get_settings_rejects_invalid_allowed_user_ids(
    monkeypatch: pytest.MonkeyPatch,
    raw_ids: str,
) -> None:
    monkeypatch.setattr("kendrick_bot.config.load_dotenv", lambda: None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", raw_ids)

    with pytest.raises(RuntimeError, match="TELEGRAM_ALLOWED_USER_IDS"):
        get_settings()
