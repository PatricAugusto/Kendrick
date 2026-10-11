import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

from kendrick_bot.telegram.handlers import (
    PENDING_ANALYSIS_KEY,
    SHOPPING_LIST_KEY,
    PendingAnalysis,
    ShoppingListItem,
    answer_item_check,
    cancel_item_check,
    show_list,
    start,
)


def test_start_greets_and_lists_available_commands() -> None:
    update, reply_text = make_update("/start")

    asyncio.run(start(update, Mock()))

    reply_text.assert_awaited_once()
    response = reply_text.await_args.args[0]
    assert response.startswith("Olá!")
    assert "Comandos disponíveis:" in response
    assert "/start —" in response
    assert "/lista —" in response
    assert "/cancelar —" in response
    assert "consumo diário" in response


def test_start_does_not_reply_when_update_has_no_message() -> None:
    update = Mock(message=None)

    assert asyncio.run(start(update, Mock())) is None


def make_update(text: str) -> tuple[Mock, AsyncMock]:
    reply_text = AsyncMock()
    message = Mock(text=text, reply_text=reply_text)
    return Mock(message=message), reply_text


def test_enough_stock_produces_analysis_without_adding_to_list() -> None:
    context = Mock(user_data={})
    replies = [
        "tomates",
        "3",
        "1",
        "3",
    ]

    for text in replies:
        update, reply_text = make_update(text)
        asyncio.run(answer_item_check(update, context))

    assert PENDING_ANALYSIS_KEY not in context.user_data
    assert SHOPPING_LIST_KEY not in context.user_data
    assert "estoque suficiente" in reply_text.await_args.args[0]
    assert "sobram 0" in reply_text.await_args.args[0]


def test_shortage_requires_confirmation_and_adds_the_missing_quantity() -> None:
    context = Mock(user_data={})
    replies = ["tomates", "3", "1", "4"]
    for text in replies:
        update, _ = make_update(text)
        asyncio.run(answer_item_check(update, context))

    pending = context.user_data[PENDING_ANALYSIS_KEY]
    assert isinstance(pending, PendingAnalysis)
    assert pending.phase == "confirm"
    assert pending.shortage == Decimal("1")

    update, reply_text = make_update("Sim")
    asyncio.run(answer_item_check(update, context))

    item = context.user_data[SHOPPING_LIST_KEY][0]
    assert item == ShoppingListItem(name="tomates", quantity=Decimal("1"))
    assert PENDING_ANALYSIS_KEY not in context.user_data
    reply_text.assert_awaited_once_with(
        "Adicionei tomates à lista. Quantidade acumulada: 1."
    )


def test_declining_confirmation_does_not_add_item() -> None:
    context = Mock(
        user_data={
            PENDING_ANALYSIS_KEY: PendingAnalysis(
                item="tomates",
                phase="confirm",
                shortage=Decimal("2"),
            )
        }
    )
    update, reply_text = make_update("Não")

    asyncio.run(answer_item_check(update, context))

    assert PENDING_ANALYSIS_KEY not in context.user_data
    assert SHOPPING_LIST_KEY not in context.user_data
    reply_text.assert_awaited_once_with("Não adicionei tomates à lista.")


def test_invalid_stock_keeps_analysis_on_stock_question() -> None:
    context = Mock(user_data={PENDING_ANALYSIS_KEY: PendingAnalysis(item="tomates")})
    update, reply_text = make_update("muitos")

    asyncio.run(answer_item_check(update, context))

    pending = context.user_data[PENDING_ANALYSIS_KEY]
    assert pending.phase == "stock"
    assert pending.stock is None
    reply_text.assert_awaited_once()


def test_decimal_comma_is_accepted_for_daily_use() -> None:
    context = Mock(
        user_data={
            PENDING_ANALYSIS_KEY: PendingAnalysis(
                item="leite",
                phase="daily_use",
                stock=Decimal("2"),
            )
        }
    )
    update, _ = make_update("0,5")

    asyncio.run(answer_item_check(update, context))

    pending = context.user_data[PENDING_ANALYSIS_KEY]
    assert pending.daily_use == Decimal("0.5")
    assert pending.phase == "days_until_shop"


def test_invalid_days_do_not_complete_analysis() -> None:
    context = Mock(
        user_data={
            PENDING_ANALYSIS_KEY: PendingAnalysis(
                item="tomates",
                phase="days_until_shop",
                stock=Decimal("3"),
                daily_use=Decimal("1"),
            )
        }
    )
    update, reply_text = make_update("3.5")

    asyncio.run(answer_item_check(update, context))

    pending = context.user_data[PENDING_ANALYSIS_KEY]
    assert pending.phase == "days_until_shop"
    assert pending.days_until_shop is None
    reply_text.assert_awaited_once()


def test_show_list_includes_suggested_quantities() -> None:
    context = Mock(
        user_data={
            SHOPPING_LIST_KEY: [
                ShoppingListItem("tomates", Decimal("1.5")),
                ShoppingListItem("arroz", Decimal("2")),
            ]
        }
    )
    update, reply_text = make_update("/lista")

    asyncio.run(show_list(update, context))

    reply_text.assert_awaited_once_with(
        "Itens para comprar:\n- tomates: 1.5\n- arroz: 2"
    )


def test_repeated_shortage_accumulates_item_quantity() -> None:
    existing_item = ShoppingListItem("tomates", Decimal("1"))
    context = Mock(
        user_data={
            SHOPPING_LIST_KEY: [existing_item],
            PENDING_ANALYSIS_KEY: PendingAnalysis(
                item="Tomates",
                phase="confirm",
                shortage=Decimal("2"),
            ),
        }
    )
    update, _ = make_update("sim")

    asyncio.run(answer_item_check(update, context))

    assert context.user_data[SHOPPING_LIST_KEY] == [
        ShoppingListItem("tomates", Decimal("3"))
    ]


def test_cancel_clears_pending_analysis() -> None:
    context = Mock(user_data={PENDING_ANALYSIS_KEY: PendingAnalysis(item="tomates")})
    update, reply_text = make_update("/cancelar")

    asyncio.run(cancel_item_check(update, context))

    assert PENDING_ANALYSIS_KEY not in context.user_data
    reply_text.assert_awaited_once_with("A análise de tomates foi cancelada.")
