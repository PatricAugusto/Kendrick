from unittest.mock import Mock, patch
from datetime import datetime, timezone

from telegram import Chat, Message, MessageEntity, Update, User
from telegram.ext import CommandHandler, MessageHandler

from kendrick_bot.config import Settings
from kendrick_bot.llm.ollama import OllamaClient
from kendrick_bot.shopping.list_store import ShoppingListStore
from kendrick_bot.telegram.application import (
    build_application,
    reject_unauthorized_user,
)
from kendrick_bot.telegram.handlers import (
    OLLAMA_CLIENT_KEY,
    SHOPPING_STORE_KEY,
    answer_item_check,
    ask_assistant,
    cancel_item_check,
    mark_item_purchased,
    show_help,
    show_list,
    start,
)

ALLOWED_USER_ID = 123456


def test_build_application_registers_start_handler() -> None:
    application = Mock()
    application.bot_data = {}
    shopping_store = Mock(spec=ShoppingListStore)
    ollama_client = Mock(spec=OllamaClient)
    builder = Mock()
    builder.token.return_value = builder
    builder.build.return_value = application
    settings = Settings(
        telegram_bot_token="test-token",
        allowed_user_ids=frozenset({ALLOWED_USER_ID}),
    )

    with patch(
        "kendrick_bot.telegram.application.Application.builder",
        return_value=builder,
    ) as application_builder, patch(
        "kendrick_bot.telegram.application.ShoppingListStore",
        return_value=shopping_store,
    ), patch(
        "kendrick_bot.telegram.application.OllamaClient",
        return_value=ollama_client,
    ):
        result = build_application(settings)

    application_builder.assert_called_once_with()
    builder.token.assert_called_once_with("test-token")
    assert result is application
    assert application.bot_data[SHOPPING_STORE_KEY] is shopping_store
    assert application.bot_data[OLLAMA_CLIENT_KEY] is ollama_client

    handlers = [call.args[0] for call in application.add_handler.call_args_list]
    command_handlers = {
        next(iter(handler.commands)): handler
        for handler in handlers
        if isinstance(handler, CommandHandler)
    }
    assert command_handlers["start"].callback is start
    assert command_handlers["ajuda"].callback is show_help
    assert command_handlers["perguntar"].callback is ask_assistant
    assert command_handlers["lista"].callback is show_list
    assert command_handlers["comprado"].callback is mark_item_purchased
    assert command_handlers["cancelar"].callback is cancel_item_check

    message_handlers = [handler for handler in handlers if isinstance(handler, MessageHandler)]
    assert len(message_handlers) == 2
    unauthorized_handler = next(
        handler for handler in message_handlers
        if handler.callback is reject_unauthorized_user
    )
    authorized_message_handler = next(
        handler for handler in message_handlers
        if handler.callback is answer_item_check
    )
    assert application.add_handler.call_args_list[0].kwargs == {"group": -1}

    allowed_update = make_update(ALLOWED_USER_ID)
    unauthorized_update = make_update(ALLOWED_USER_ID + 1)
    group_update = make_update(ALLOWED_USER_ID, chat_type=Chat.GROUP)
    assert authorized_message_handler.check_update(allowed_update)
    assert not authorized_message_handler.check_update(unauthorized_update)
    assert not authorized_message_handler.check_update(group_update)
    assert unauthorized_handler.check_update(unauthorized_update)
    assert unauthorized_handler.check_update(group_update)
    for handler in command_handlers.values():
        assert handler.filters.check_update(make_update(ALLOWED_USER_ID))
        assert not handler.filters.check_update(make_update(ALLOWED_USER_ID + 1))
        assert not handler.filters.check_update(
            make_update(ALLOWED_USER_ID, chat_type=Chat.GROUP)
        )


def make_update(
    user_id: int,
    *,
    chat_type: str = Chat.PRIVATE,
    text: str = "tomates",
) -> Update:
    user = User(id=user_id, is_bot=False, first_name="Test")
    chat = Chat(id=user_id, type=chat_type)
    message = Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=user,
        text=text,
        entities=(
            [
                MessageEntity(
                    type=MessageEntity.BOT_COMMAND,
                    offset=0,
                    length=text.index(" ") if " " in text else len(text),
                )
            ]
            if text.startswith("/")
            else None
        ),
    )
    return Update(update_id=1, message=message)
