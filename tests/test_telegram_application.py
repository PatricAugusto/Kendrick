from unittest.mock import Mock, patch

from telegram.ext import CommandHandler, MessageHandler

from kendrick_bot.config import Settings
from kendrick_bot.telegram.application import build_application
from kendrick_bot.telegram.handlers import (
    answer_item_check,
    cancel_item_check,
    show_list,
    start,
)


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

    handlers = [call.args[0] for call in application.add_handler.call_args_list]
    command_handlers = {
        next(iter(handler.commands)): handler
        for handler in handlers
        if isinstance(handler, CommandHandler)
    }
    assert command_handlers["start"].callback is start
    assert command_handlers["lista"].callback is show_list
    assert command_handlers["cancelar"].callback is cancel_item_check

    message_handlers = [handler for handler in handlers if isinstance(handler, MessageHandler)]
    assert len(message_handlers) == 1
    assert message_handlers[0].callback is answer_item_check
