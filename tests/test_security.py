import logging
import asyncio
from io import StringIO
from unittest.mock import AsyncMock, Mock, patch

from kendrick_bot.security import (
    SecretRedactionFilter,
    configure_logging,
)
from kendrick_bot.telegram.application import reject_unauthorized_user


def test_secret_redaction_filter_removes_token_from_exception_logs() -> None:
    secret = "test-secret-token"
    output = StringIO()
    handler = logging.StreamHandler(output)
    handler.addFilter(SecretRedactionFilter(secret))
    logger = logging.getLogger("security-test")
    logger.addHandler(handler)
    logger.propagate = False

    try:
        try:
            raise RuntimeError(f"Invalid token: {secret}")
        except RuntimeError:
            logger.exception("Telegram request failed")
    finally:
        logger.removeHandler(handler)
        logger.propagate = True
        handler.close()

    assert secret not in output.getvalue()
    assert "Telegram request failed" in output.getvalue()


def test_configure_logging_installs_redaction_filter_and_suppresses_httpx_info() -> None:
    root_logger = Mock()
    handler = Mock()
    root_logger.handlers = [handler]
    httpx_logger = Mock()

    def get_logger(name: str | None = None) -> Mock:
        return root_logger if name is None else httpx_logger

    with (
        patch("kendrick_bot.security.logging.basicConfig") as basic_config,
        patch("kendrick_bot.security.logging.getLogger", side_effect=get_logger),
    ):
        configure_logging("test-secret-token")

    basic_config.assert_called_once()
    redaction_filter = handler.addFilter.call_args.args[0]
    assert isinstance(redaction_filter, SecretRedactionFilter)
    httpx_logger.setLevel.assert_called_once_with(logging.WARNING)


def test_unauthorized_user_receives_access_denied_without_state_access() -> None:
    message = Mock(reply_text=AsyncMock())
    update = Mock(message=message)
    context = Mock(user_data={"shopping_list": ["private item"]})

    asyncio.run(reject_unauthorized_user(update, context))

    message.reply_text.assert_awaited_once_with(
        "Acesso não autorizado. Este bot é privado."
    )
    assert context.user_data == {"shopping_list": ["private item"]}
