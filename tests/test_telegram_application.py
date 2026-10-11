from unittest.mock import Mock, patch

from telegram.ext import CommandHandler

from kendrick_bot.config import Settings
from kendrick_bot.telegram.application import build_application
from kendrick_bot.telegram.handlers import start


def test_build_application_registers_start_handler() -> None:
    application = Mock()
    builder = Mock()
    builder.token.return_value = builder
    builder.build.return_value = application
    settings = Settings(telegram_bot_token="test-token")

    with patch(
        "kendrick_bot.telegram.application.Application.builder",
        return_value=builder,
    ) as application_builder:
        result = build_application(settings)

    application_builder.assert_called_once_with()
    builder.token.assert_called_once_with("test-token")
    assert result is application

    handler = application.add_handler.call_args.args[0]
    assert isinstance(handler, CommandHandler)
    assert handler.callback is start
    assert "start" in handler.commands
