from unittest.mock import Mock, patch

import pytest
from telegram.error import InvalidToken

from kendrick_bot import __main__ as entrypoint
from kendrick_bot.config import Settings


def test_main_builds_and_runs_the_telegram_application() -> None:
    settings = Settings(telegram_bot_token="test-token")
    application = Mock()

    with (
        patch.object(entrypoint.logging, "basicConfig") as configure_logging,
        patch.object(entrypoint, "get_settings", return_value=settings) as get_settings,
        patch.object(
            entrypoint,
            "build_application",
            return_value=application,
        ) as build_application,
    ):
        entrypoint.main()

    configure_logging.assert_called_once()
    get_settings.assert_called_once_with()
    build_application.assert_called_once_with(settings)
    application.run_polling.assert_called_once_with()


def test_main_shows_sanitized_error_when_telegram_rejects_token() -> None:
    application = Mock()
    application.run_polling.side_effect = InvalidToken(
        "The token `secret-token` was rejected by the server."
    )

    with (
        patch.object(entrypoint.logging, "basicConfig"),
        patch.object(
            entrypoint,
            "get_settings",
            return_value=Settings(telegram_bot_token="secret-token"),
        ),
        patch.object(entrypoint, "build_application", return_value=application),
        pytest.raises(SystemExit) as error,
    ):
        entrypoint.main()

    assert "revogue-o no @BotFather" in str(error.value)
    assert "secret-token" not in str(error.value)
