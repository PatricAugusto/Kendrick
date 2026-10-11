import pytest

from kendrick_bot.config import Settings, get_settings


def test_get_settings_reads_telegram_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kendrick_bot.config.load_dotenv", lambda: None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "123, 456")

    assert get_settings() == Settings(
        telegram_bot_token="test-token",
        allowed_user_ids=frozenset({123, 456}),
    )


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
