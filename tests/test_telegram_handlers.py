import asyncio
from unittest.mock import AsyncMock, Mock

from kendrick_bot.telegram.handlers import start


def test_start_replies_with_welcome_message() -> None:
    message = Mock()
    message.reply_text = AsyncMock()
    update = Mock(message=message)

    asyncio.run(start(update, Mock()))

    message.reply_text.assert_awaited_once_with(
        "Olá! Sou seu assistente de compras. "
        "Por enquanto estou aprendendo a conversar; em breve vamos montar sua lista."
    )


def test_start_does_not_reply_when_update_has_no_message() -> None:
    update = Mock(message=None)

    assert asyncio.run(start(update, Mock())) is None
