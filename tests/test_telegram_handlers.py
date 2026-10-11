import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

from kendrick_bot.llm.ollama import OllamaError
from kendrick_bot.shopping.pantry_store import PantryItem
from kendrick_bot.telegram.handlers import (
    OLLAMA_CLIENT_KEY,
    PANTRY_STORE_KEY,
    PENDING_ANALYSIS_KEY,
    SHOPPING_STORE_KEY,
    PendingAnalysis,
    ShoppingListItem,
    answer_item_check,
    ask_assistant,
    cancel_item_check,
    mark_item_purchased,
    remove_pantry_item,
    set_pantry_consumption,
    set_pantry_stock,
    show_help,
    show_list,
    show_pantry,
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
    assert "/ajuda —" in response
    assert "/perguntar <dúvida> —" in response
    assert "/lista —" in response
    assert "/comprado <item> <quantidade> —" in response
    assert "/despensa —" in response
    assert "/estoque <item> <quantidade> <unidade> —" in response
    assert "/consumo <item> <quantidade> <unidade>/dia —" in response
    assert "/remover_despensa <item> confirmar —" in response
    assert "/cancelar —" in response
    assert "consumo diário" in response


def test_help_lists_commands_and_usage() -> None:
    update, reply_text = make_update("/ajuda")

    asyncio.run(show_help(update, Mock()))

    reply_text.assert_awaited_once()
    response = reply_text.await_args.args[0]
    assert "Comandos disponíveis:" in response
    assert "/ajuda —" in response
    assert "/perguntar <dúvida> —" in response
    assert "/lista —" in response
    assert "/comprado <item> <quantidade> —" in response
    assert "/despensa —" in response
    assert "/estoque <item> <quantidade> <unidade> —" in response
    assert "/consumo <item> <quantidade> <unidade>/dia —" in response
    assert "/remover_despensa <item> confirmar —" in response
    assert "/cancelar —" in response
    assert "Se houver falta" in response


def test_help_does_not_reply_when_update_has_no_message() -> None:
    update = Mock(message=None)

    assert asyncio.run(show_help(update, Mock())) is None


def test_start_does_not_reply_when_update_has_no_message() -> None:
    update = Mock(message=None)

    assert asyncio.run(start(update, Mock())) is None


def make_update(text: str) -> tuple[Mock, AsyncMock]:
    reply_text = AsyncMock()
    message = Mock(text=text, reply_text=reply_text)
    return Mock(message=message, effective_user=Mock(id=123456)), reply_text


def make_command_context(store: Mock, args: list[str]) -> Mock:
    return Mock(
        user_data={},
        bot_data={SHOPPING_STORE_KEY: store},
        args=args,
    )


def make_pantry_context(store: Mock, args: list[str]) -> Mock:
    return Mock(
        user_data={},
        bot_data={PANTRY_STORE_KEY: store},
        args=args,
    )


def test_show_pantry_displays_stock_and_consumption() -> None:
    store = Mock()
    store.get_items.return_value = [
        PantryItem(
            name="arroz",
            quantity=Decimal("2.5"),
            unit="kg",
            daily_consumption=Decimal("0.1"),
        ),
        PantryItem(
            name="leite",
            quantity=Decimal("1"),
            unit="L",
            daily_consumption=None,
        ),
    ]
    context = make_pantry_context(store, [])
    update, reply_text = make_update("/despensa")

    asyncio.run(show_pantry(update, context))

    store.get_items.assert_called_once_with(123456)
    reply_text.assert_awaited_once_with(
        "Sua despensa:\n"
        "- arroz: 2.5 kg; consumo: 0.1 kg/dia\n"
        "- leite: 1 L; consumo: consumo não informado"
    )


def test_show_pantry_reports_empty_pantry() -> None:
    store = Mock()
    store.get_items.return_value = []
    context = make_pantry_context(store, [])
    update, reply_text = make_update("/despensa")

    asyncio.run(show_pantry(update, context))

    reply_text.assert_awaited_once()
    assert "ainda não tem itens" in reply_text.await_args.args[0]


def test_set_pantry_stock_accepts_multword_item_and_decimal_comma() -> None:
    store = Mock()
    store.set_stock.return_value = PantryItem(
        name="arroz integral",
        quantity=Decimal("2.5"),
        unit="kg",
        daily_consumption=None,
    )
    context = make_pantry_context(store, ["arroz", "integral", "2,5", "kg"])
    update, reply_text = make_update("/estoque arroz integral 2,5 kg")

    asyncio.run(set_pantry_stock(update, context))

    store.set_stock.assert_called_once_with(
        123456,
        "arroz integral",
        Decimal("2.5"),
        "kg",
    )
    reply_text.assert_awaited_once_with("Estoque de arroz integral atualizado: 2.5 kg.")


def test_set_pantry_stock_rejects_negative_quantity() -> None:
    store = Mock()
    context = make_pantry_context(store, ["arroz", "-1", "kg"])
    update, reply_text = make_update("/estoque arroz -1 kg")

    asyncio.run(set_pantry_stock(update, context))

    store.set_stock.assert_not_called()
    reply_text.assert_awaited_once()
    assert "inválidos" in reply_text.await_args.args[0]


def test_set_pantry_stock_reports_unsafe_precision_or_magnitude() -> None:
    from kendrick_bot.shopping.pantry_store import PantryInvalidQuantity

    store = Mock()
    store.set_stock.side_effect = PantryInvalidQuantity
    context = make_pantry_context(store, ["arroz", "1e100", "kg"])
    update, reply_text = make_update("/estoque arroz 1e100 kg")

    asyncio.run(set_pantry_stock(update, context))

    reply_text.assert_awaited_once()
    assert "seis casas decimais" in reply_text.await_args.args[0]


def test_set_pantry_stock_reports_unit_mismatch() -> None:
    from kendrick_bot.shopping.pantry_store import PantryUnitMismatch

    store = Mock()
    store.set_stock.side_effect = PantryUnitMismatch
    context = make_pantry_context(store, ["arroz", "2", "unidades"])
    update, reply_text = make_update("/estoque arroz 2 unidades")

    asyncio.run(set_pantry_stock(update, context))

    reply_text.assert_awaited_once()
    assert "outra unidade" in reply_text.await_args.args[0]


def test_set_pantry_consumption_requires_daily_period() -> None:
    store = Mock()
    context = make_pantry_context(store, ["arroz", "0,1", "kg"])
    update, reply_text = make_update("/consumo arroz 0,1 kg")

    asyncio.run(set_pantry_consumption(update, context))

    store.set_daily_consumption.assert_not_called()
    reply_text.assert_awaited_once()
    assert "por dia" in reply_text.await_args.args[0]


def test_set_pantry_consumption_rejects_zero() -> None:
    store = Mock()
    context = make_pantry_context(store, ["arroz", "0", "kg/dia"])
    update, reply_text = make_update("/consumo arroz 0 kg/dia")

    asyncio.run(set_pantry_consumption(update, context))

    store.set_daily_consumption.assert_not_called()
    reply_text.assert_awaited_once()
    assert "maior que zero" in reply_text.await_args.args[0]


def test_set_pantry_consumption_stores_daily_amount() -> None:
    store = Mock()
    store.set_daily_consumption.return_value = PantryItem(
        name="arroz",
        quantity=Decimal("2"),
        unit="kg",
        daily_consumption=Decimal("0.1"),
    )
    context = make_pantry_context(store, ["arroz", "0,1", "kg/dia"])
    update, reply_text = make_update("/consumo arroz 0,1 kg/dia")

    asyncio.run(set_pantry_consumption(update, context))

    store.set_daily_consumption.assert_called_once_with(
        123456,
        "arroz",
        Decimal("0.1"),
        "kg",
    )
    reply_text.assert_awaited_once_with(
        "Consumo diário de arroz atualizado: 0.1 kg/dia."
    )


def test_set_pantry_consumption_requires_item_to_be_registered() -> None:
    from kendrick_bot.shopping.pantry_store import PantryItemNotFound

    store = Mock()
    store.set_daily_consumption.side_effect = PantryItemNotFound
    context = make_pantry_context(store, ["arroz", "0,1", "kg/dia"])
    update, reply_text = make_update("/consumo arroz 0,1 kg/dia")

    asyncio.run(set_pantry_consumption(update, context))

    reply_text.assert_awaited_once()
    assert "Cadastre primeiro" in reply_text.await_args.args[0]


def test_remove_pantry_item_removes_registered_entry() -> None:
    store = Mock()
    store.remove_item.return_value = True
    context = make_pantry_context(store, ["arroz", "integral", "confirmar"])
    update, reply_text = make_update("/remover_despensa arroz integral confirmar")

    asyncio.run(remove_pantry_item(update, context))

    store.remove_item.assert_called_once_with(123456, "arroz integral")
    reply_text.assert_awaited_once()
    assert "não altera sua lista de compras" in reply_text.await_args.args[0]


def test_remove_pantry_item_reports_unknown_entry() -> None:
    store = Mock()
    store.remove_item.return_value = False
    context = make_pantry_context(store, ["arroz", "confirmar"])
    update, reply_text = make_update("/remover_despensa arroz confirmar")

    asyncio.run(remove_pantry_item(update, context))

    reply_text.assert_awaited_once()
    assert "não está cadastrado" in reply_text.await_args.args[0]


def test_remove_pantry_item_requires_explicit_confirmation() -> None:
    store = Mock()
    context = make_pantry_context(store, ["arroz"])
    update, reply_text = make_update("/remover_despensa arroz")

    asyncio.run(remove_pantry_item(update, context))

    store.remove_item.assert_not_called()
    reply_text.assert_awaited_once()
    assert "confirmar" in reply_text.await_args.args[0]


def test_pantry_command_handlers_persist_data_end_to_end(tmp_path) -> None:
    from kendrick_bot.shopping.pantry_store import PantryStore

    store = PantryStore(tmp_path / "kendrick.sqlite3")
    stock_context = make_pantry_context(store, ["arroz", "2,5", "kg"])
    stock_update, stock_reply = make_update("/estoque arroz 2,5 kg")
    asyncio.run(set_pantry_stock(stock_update, stock_context))

    consumption_context = make_pantry_context(
        store,
        ["arroz", "0,1", "kg/dia"],
    )
    consumption_update, consumption_reply = make_update(
        "/consumo arroz 0,1 kg/dia"
    )
    asyncio.run(set_pantry_consumption(consumption_update, consumption_context))

    pantry_context = make_pantry_context(PantryStore(store.database_path), [])
    pantry_update, pantry_reply = make_update("/despensa")
    asyncio.run(show_pantry(pantry_update, pantry_context))

    stock_reply.assert_awaited_once()
    consumption_reply.assert_awaited_once()
    pantry_reply.assert_awaited_once_with(
        "Sua despensa:\n- arroz: 2.5 kg; consumo: 0.1 kg/dia"
    )


def test_ask_assistant_sends_question_to_local_model() -> None:
    client = Mock()
    client.ask = AsyncMock(return_value="Planeje o cardápio antes de comprar.")
    context = Mock(bot_data={OLLAMA_CLIENT_KEY: client}, args=["como", "planejar?"])
    update, reply_text = make_update("/perguntar como planejar?")

    asyncio.run(ask_assistant(update, context))

    client.ask.assert_awaited_once_with("como planejar?")
    reply_text.assert_awaited_once_with("Planeje o cardápio antes de comprar.")


def test_ask_assistant_requests_question_when_missing() -> None:
    client = Mock()
    context = Mock(bot_data={OLLAMA_CLIENT_KEY: client}, args=[])
    update, reply_text = make_update("/perguntar")

    asyncio.run(ask_assistant(update, context))

    client.ask.assert_not_called()
    reply_text.assert_awaited_once()
    assert "/perguntar" in reply_text.await_args.args[0]


def test_ask_assistant_reports_local_model_unavailable() -> None:
    client = Mock()
    client.ask = AsyncMock(side_effect=OllamaError("not available"))
    context = Mock(bot_data={OLLAMA_CLIENT_KEY: client}, args=["dúvida"])
    update, reply_text = make_update("/perguntar dúvida")

    asyncio.run(ask_assistant(update, context))

    reply_text.assert_awaited_once()
    assert "Ollama" in reply_text.await_args.args[0]


def test_enough_stock_produces_analysis_without_adding_to_list() -> None:
    store = Mock()
    context = make_context(store)
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
    store.add_quantity.assert_not_called()
    assert "estoque suficiente" in reply_text.await_args.args[0]
    assert "sobram 0" in reply_text.await_args.args[0]


def test_shortage_requires_confirmation_and_adds_the_missing_quantity() -> None:
    store = Mock()
    store.add_quantity.return_value = Decimal("1")
    context = make_context(store)
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

    store.add_quantity.assert_called_once_with(123456, "tomates", Decimal("1"))
    assert PENDING_ANALYSIS_KEY not in context.user_data
    reply_text.assert_awaited_once_with(
        "Adicionei tomates à lista. Quantidade acumulada: 1."
    )


def test_declining_confirmation_does_not_add_item() -> None:
    store = Mock()
    context = Mock(
        user_data={
            PENDING_ANALYSIS_KEY: PendingAnalysis(
                item="tomates",
                phase="confirm",
                shortage=Decimal("2"),
            )
        },
        bot_data={SHOPPING_STORE_KEY: store},
    )
    update, reply_text = make_update("Não")

    asyncio.run(answer_item_check(update, context))

    assert PENDING_ANALYSIS_KEY not in context.user_data
    store.add_quantity.assert_not_called()
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
    store = Mock(
        get_items=Mock(
            return_value=[
                ShoppingListItem("tomates", Decimal("1.5")),
                ShoppingListItem("arroz", Decimal("2")),
            ]
        )
    )
    context = make_context(store)
    update, reply_text = make_update("/lista")

    asyncio.run(show_list(update, context))

    store.get_items.assert_called_once_with(123456)
    reply_text.assert_awaited_once_with(
        "Itens para comprar:\n- tomates: 1.5\n- arroz: 2"
    )


def test_mark_item_purchased_subtracts_quantity() -> None:
    store = Mock()
    store.mark_purchased.return_value = Decimal("1.5")
    context = make_command_context(store, ["tomates", "0,5"])
    update, reply_text = make_update("/comprado tomates 0,5")

    asyncio.run(mark_item_purchased(update, context))

    store.mark_purchased.assert_called_once_with(
        123456,
        "tomates",
        Decimal("0.5"),
    )
    reply_text.assert_awaited_once_with(
        "Marquei 0.5 de tomates como comprado. Restam 1.5 na lista."
    )


def test_mark_item_purchased_supports_item_names_with_spaces() -> None:
    store = Mock()
    store.mark_purchased.return_value = Decimal("0")
    context = make_command_context(store, ["leite", "integral", "2"])
    update, reply_text = make_update("/comprado leite integral 2")

    asyncio.run(mark_item_purchased(update, context))

    store.mark_purchased.assert_called_once_with(
        123456,
        "leite integral",
        Decimal("2"),
    )
    reply_text.assert_awaited_once_with(
        "Marquei leite integral como comprado e removi da lista."
    )


def test_mark_item_purchased_requires_item_and_quantity() -> None:
    store = Mock()
    context = make_command_context(store, ["tomates"])
    update, reply_text = make_update("/comprado tomates")

    asyncio.run(mark_item_purchased(update, context))

    store.mark_purchased.assert_not_called()
    reply_text.assert_awaited_once_with(
        "Use /comprado <item> <quantidade>. "
        "Exemplo: /comprado tomates 2"
    )


def test_mark_item_purchased_rejects_invalid_quantity() -> None:
    store = Mock()
    context = make_command_context(store, ["tomates", "0"])
    update, reply_text = make_update("/comprado tomates 0")

    asyncio.run(mark_item_purchased(update, context))

    store.mark_purchased.assert_not_called()
    reply_text.assert_awaited_once()
    assert "Quantidade inválida" in reply_text.await_args.args[0]


def test_mark_item_purchased_reports_item_not_on_list() -> None:
    store = Mock()
    store.mark_purchased.return_value = None
    context = make_command_context(store, ["tomates", "1"])
    update, reply_text = make_update("/comprado tomates 1")

    asyncio.run(mark_item_purchased(update, context))

    reply_text.assert_awaited_once_with(
        "tomates não está na sua lista de compras."
    )


def test_mark_item_purchased_reports_when_quantity_exceeds_listed() -> None:
    from kendrick_bot.shopping.list_store import InsufficientListedQuantity

    store = Mock()
    store.mark_purchased.side_effect = InsufficientListedQuantity
    context = make_command_context(store, ["tomates", "3"])
    update, reply_text = make_update("/comprado tomates 3")

    asyncio.run(mark_item_purchased(update, context))

    reply_text.assert_awaited_once_with(
        "Não é possível marcar 3 de tomates como comprado: "
        "a quantidade excede o que está na lista."
    )


def test_repeated_shortage_accumulates_item_quantity() -> None:
    store = Mock()
    store.add_quantity.return_value = Decimal("3")
    context = Mock(
        user_data={
            PENDING_ANALYSIS_KEY: PendingAnalysis(
                item="Tomates",
                phase="confirm",
                shortage=Decimal("2"),
            ),
        },
        bot_data={SHOPPING_STORE_KEY: store},
    )
    update, _ = make_update("sim")

    asyncio.run(answer_item_check(update, context))

    store.add_quantity.assert_called_once_with(123456, "Tomates", Decimal("2"))


def test_cancel_clears_pending_analysis() -> None:
    context = Mock(user_data={PENDING_ANALYSIS_KEY: PendingAnalysis(item="tomates")})
    update, reply_text = make_update("/cancelar")

    asyncio.run(cancel_item_check(update, context))

    assert PENDING_ANALYSIS_KEY not in context.user_data
    reply_text.assert_awaited_once_with("A análise de tomates foi cancelada.")


def make_context(store: Mock) -> Mock:
    return Mock(user_data={}, bot_data={SHOPPING_STORE_KEY: store})
