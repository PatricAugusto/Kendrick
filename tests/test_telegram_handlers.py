import asyncio
from unittest.mock import AsyncMock, Mock

from kendrick_bot.telegram.handlers import (
    PENDING_ITEM_KEY,
    SHOPPING_LIST_KEY,
    answer_item_check,
    cancel_item_check,
    check_item,
    show_list,
    start,
)


def test_start_replies_with_welcome_message() -> None:
    message = Mock()
    message.reply_text = AsyncMock()
    update = Mock(message=message)

    asyncio.run(start(update, Mock()))

    message.reply_text.assert_awaited_once_with(
        "Olá! Envie o nome de um item para avaliarmos se precisa entrar na lista. "
        "Vou perguntar se seu estoque atual dura até a próxima compra. "
        "Use /lista para consultar os itens ou /cancelar para interromper uma avaliação."
    )


def test_start_does_not_reply_when_update_has_no_message() -> None:
    update = Mock(message=None)

    assert asyncio.run(start(update, Mock())) is None


def make_update(text: str) -> tuple[Mock, AsyncMock]:
    reply_text = AsyncMock()
    message = Mock(text=text, reply_text=reply_text)
    return Mock(message=message), reply_text


def test_check_item_asks_if_stock_lasts_until_next_shop() -> None:
    update, reply_text = make_update("cotonete")
    context = Mock(user_data={})

    asyncio.run(check_item(update, context))

    assert context.user_data[PENDING_ITEM_KEY] == "cotonete"
    reply_text.assert_awaited_once_with(
        "Vamos avaliar cotonete: o que você tem em casa dura até a próxima compra? "
        "Responda Sim ou Não."
    )


def test_answer_sim_does_not_add_item_to_shopping_list() -> None:
    update, reply_text = make_update("Sim")
    context = Mock(user_data={PENDING_ITEM_KEY: "cotonete"})

    asyncio.run(answer_item_check(update, context))

    assert PENDING_ITEM_KEY not in context.user_data
    assert SHOPPING_LIST_KEY not in context.user_data
    reply_text.assert_awaited_once_with(
        "Seu estoque de cotonete dura até a próxima compra; não adicionei à lista."
    )


def test_answer_nao_adds_item_to_shopping_list() -> None:
    update, reply_text = make_update("Não")
    context = Mock(user_data={PENDING_ITEM_KEY: "cotonete"})

    asyncio.run(answer_item_check(update, context))

    assert context.user_data[SHOPPING_LIST_KEY] == ["cotonete"]
    assert PENDING_ITEM_KEY not in context.user_data
    reply_text.assert_awaited_once_with(
        "Como o estoque não dura, adicionei cotonete à lista."
    )


def test_invalid_answer_keeps_item_pending() -> None:
    update, reply_text = make_update("talvez")
    context = Mock(user_data={PENDING_ITEM_KEY: "cotonete"})

    asyncio.run(answer_item_check(update, context))

    assert context.user_data[PENDING_ITEM_KEY] == "cotonete"
    reply_text.assert_awaited_once()


def test_repeated_item_is_not_added_twice() -> None:
    update, reply_text = make_update("Não")
    context = Mock(
        user_data={
            PENDING_ITEM_KEY: "Cotonete",
            SHOPPING_LIST_KEY: ["cotonete"],
        }
    )

    asyncio.run(answer_item_check(update, context))

    assert context.user_data[SHOPPING_LIST_KEY] == ["cotonete"]
    reply_text.assert_awaited_once_with("Cotonete já está na lista de compras.")


def test_show_list_formats_items() -> None:
    update, reply_text = make_update("/lista")
    context = Mock(user_data={SHOPPING_LIST_KEY: ["cotonete", "arroz"]})

    asyncio.run(show_list(update, context))

    reply_text.assert_awaited_once_with("Itens para comprar:\n- cotonete\n- arroz")


def test_cancel_clears_pending_item() -> None:
    update, reply_text = make_update("/cancelar")
    context = Mock(user_data={PENDING_ITEM_KEY: "cotonete"})

    asyncio.run(cancel_item_check(update, context))

    assert PENDING_ITEM_KEY not in context.user_data
    reply_text.assert_awaited_once_with("A avaliação de cotonete foi cancelada.")
