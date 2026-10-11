from unittest.mock import Mock, patch

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
