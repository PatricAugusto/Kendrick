import pytest

from kendrick_bot.config import Settings, get_settings


def test_get_settings_reads_telegram_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kendrick_bot.config.load_dotenv", lambda: None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    assert get_settings() == Settings(telegram_bot_token="test-token")


def test_get_settings_fails_when_telegram_token_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("kendrick_bot.config.load_dotenv", lambda: None)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="Token do Telegram não configurado"):
        get_settings()
