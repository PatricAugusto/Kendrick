import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from telegram import Update
from telegram.ext import ContextTypes

from kendrick_bot.llm.ollama import OllamaClient, OllamaError
from kendrick_bot.shopping.forecast import StockForecast, forecast_stock
from kendrick_bot.shopping.pantry_store import (
    PantryInvalidQuantity,
    PantryItemNotFound,
    PantryStore,
    PantryUnitMismatch,
)
from kendrick_bot.shopping.list_store import (
    InsufficientListedQuantity,
    ShoppingListItem,
    ShoppingListStore,
)

PENDING_ANALYSIS_KEY = "pending_stock_analysis"
SHOPPING_STORE_KEY = "shopping_list_store"
OLLAMA_CLIENT_KEY = "ollama_client"
PANTRY_STORE_KEY = "pantry_store"
HELP_TEXT = (
    "Comandos disponíveis:\n"
    "/start — ver a saudação e esta ajuda.\n"
    "/ajuda — consultar os comandos e como usar o Kendrick.\n"
    "/perguntar <dúvida> — pedir uma sugestão ao assistente.\n"
    "/despensa — consultar os itens, estoques e consumos cadastrados.\n"
    "/estoque <item> <quantidade> <unidade> — cadastrar ou atualizar o estoque.\n"
    "/consumo <item> <quantidade> <unidade>/dia — registrar o consumo habitual.\n"
    "/remover_despensa <item> confirmar — remover um item da despensa.\n"
    "/lista — consultar os itens e as quantidades para comprar.\n"
    "/comprado <item> <quantidade> — registrar o que já foi comprado.\n"
    "/cancelar — interromper a análise em andamento.\n\n"
    "Para analisar um item, envie o nome dele. Vou perguntar a quantidade "
    "em estoque, o consumo diário e em quantos dias será a próxima compra. "
    "Se houver falta, posso adicionar à lista após sua confirmação.\n\n"
    "No /comprado, informe um item que já esteja na lista e a quantidade "
    "comprada. Quantidades decimais podem usar vírgula.\n\n"
    "Na despensa, use unidades consistentes, como `/estoque arroz 2 kg` e "
    "`/consumo arroz 0,1 kg/dia`. O consumo deve usar a mesma unidade "
    "cadastrada no estoque."
)


@dataclass
class PendingAnalysis:
    item: str
    phase: Literal["stock", "daily_use", "days_until_shop", "confirm"] = "stock"
    stock: Decimal | None = None
    daily_use: Decimal | None = None
    days_until_shop: int | None = None
    shortage: Decimal | None = None


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "Olá! Eu sou o Kendrick, seu assistente para organizar as compras.\n\n"
        + HELP_TEXT
    )


async def show_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    await update.message.reply_text(HELP_TEXT)


async def show_pantry(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    store: PantryStore = context.bot_data[PANTRY_STORE_KEY]
    pantry_items = store.get_items(user.id)
    if not pantry_items:
        await update.message.reply_text(
            "Sua despensa ainda não tem itens cadastrados. "
            "Use /estoque <item> <quantidade> <unidade> para começar."
        )
        return

    lines = []
    for item in pantry_items:
        consumption = (
            f"{_format_quantity(item.daily_consumption)} {item.unit}/dia"
            if item.daily_consumption is not None
            else "consumo não informado"
        )
        lines.append(
            f"- {item.name}: {_format_quantity(item.quantity)} "
            f"{item.unit}; consumo: {consumption}"
        )
    await update.message.reply_text("Sua despensa:\n" + "\n".join(lines))


async def set_pantry_stock(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    parsed = _parse_item_quantity_unit(context.args)
    if parsed is None:
        await update.message.reply_text(
            "Use /estoque <item> <quantidade> <unidade>. "
            "Exemplo: /estoque arroz 2 kg"
        )
        return
    item_name, quantity, unit = parsed
    if (
        not _valid_pantry_name(item_name)
        or not _valid_pantry_unit(unit)
        or quantity is None
        or quantity < 0
    ):
        await update.message.reply_text(
            "Item, unidade ou quantidade inválidos. Informe um estoque maior "
            "ou igual a zero e uma unidade como kg, L ou unidades."
        )
        return

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    store: PantryStore = context.bot_data[PANTRY_STORE_KEY]
    try:
        item = store.set_stock(user.id, item_name, quantity, unit)
    except PantryInvalidQuantity:
        await update.message.reply_text(
            "Quantidade inválida. Use um número entre zero e "
            "999999999999, com no máximo seis casas decimais."
        )
        return
    except PantryUnitMismatch:
        await update.message.reply_text(
            f"{item_name} já está cadastrado com outra unidade. "
            "Remova-o da despensa e cadastre novamente para trocar a unidade."
        )
        return

    await update.message.reply_text(
        f"Estoque de {item.name} atualizado: "
        f"{_format_quantity(item.quantity)} {item.unit}."
    )


async def set_pantry_consumption(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    parsed = _parse_item_quantity_unit(context.args)
    if parsed is None:
        await update.message.reply_text(
            "Use /consumo <item> <quantidade> <unidade>/dia. "
            "Exemplo: /consumo arroz 0,1 kg/dia"
        )
        return
    item_name, quantity, raw_unit = parsed
    if not _valid_pantry_name(item_name) or quantity is None or quantity <= 0:
        await update.message.reply_text(
            "Item, unidade ou consumo inválidos. Informe um consumo diário "
            "maior que zero, como 0,1 kg/dia."
        )
        return
    if not raw_unit.casefold().endswith("/dia"):
        await update.message.reply_text(
            "Informe o consumo por dia, por exemplo: "
            "/consumo arroz 0,1 kg/dia"
        )
        return

    unit = raw_unit[:-4]
    if not _valid_pantry_unit(unit):
        await update.message.reply_text(
            "Unidade inválida. Use uma unidade como kg, L ou unidades."
        )
        return

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    store: PantryStore = context.bot_data[PANTRY_STORE_KEY]
    try:
        item = store.set_daily_consumption(user.id, item_name, quantity, unit)
    except PantryInvalidQuantity:
        await update.message.reply_text(
            "Consumo inválido. Use um número maior que zero e menor que "
            "1000000000000, com no máximo seis casas decimais."
        )
        return
    except PantryItemNotFound:
        await update.message.reply_text(
            f"{item_name} ainda não está na despensa. Cadastre primeiro com "
            "/estoque <item> <quantidade> <unidade>."
        )
        return
    except PantryUnitMismatch:
        await update.message.reply_text(
            f"A unidade de consumo de {item_name} deve ser igual à unidade "
            "cadastrada no estoque."
        )
        return

    await update.message.reply_text(
        f"Consumo diário de {item.name} atualizado: "
        f"{_format_quantity(quantity)} {item.unit}/dia."
    )


async def remove_pantry_item(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    args = context.args
    if len(args) < 2 or args[-1].casefold() != "confirmar":
        await update.message.reply_text(
            "Para confirmar a remoção, use /remover_despensa <item> confirmar. "
            "Exemplo: /remover_despensa arroz confirmar"
        )
        return
    item_name = " ".join(args[:-1]).strip()
    if not _valid_pantry_name(item_name):
        await update.message.reply_text(
            "Informe o nome do item. Exemplo: /remover_despensa arroz confirmar"
        )
        return

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    store: PantryStore = context.bot_data[PANTRY_STORE_KEY]
    if not store.remove_item(user.id, item_name):
        await update.message.reply_text(
            f"{item_name} não está cadastrado na sua despensa."
        )
        return
    await update.message.reply_text(
        f"Removi {item_name} da despensa. Isso não altera sua lista de compras."
    )


async def ask_assistant(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    question = " ".join(context.args).strip()
    if not question:
        await update.message.reply_text(
            "Escreva sua dúvida depois do comando. "
            "Exemplo: /perguntar como organizar as compras da semana?"
        )
        return

    client: OllamaClient = context.bot_data[OLLAMA_CLIENT_KEY]
    try:
        answer = await client.ask(question)
    except OllamaError:
        await update.message.reply_text(
            "Não consegui obter uma resposta do modelo local. Confira se o "
            "Ollama está aberto e se o modelo configurado está instalado."
        )
        return

    await update.message.reply_text(answer)


async def answer_item_check(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None or update.message.text is None:
        return

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Envie o nome de um item para analisar.")
        return

    pending = context.user_data.get(PENDING_ANALYSIS_KEY)
    if not isinstance(pending, PendingAnalysis):
        context.user_data[PENDING_ANALYSIS_KEY] = PendingAnalysis(item=text)
        await update.message.reply_text(
            f"Vamos analisar {text}. Quanto você tem em estoque? "
            "Envie apenas a quantidade (por exemplo, 3). Use a mesma unidade "
            "para as próximas quantidades, como unidades ou kg."
        )
        return

    if pending.phase == "stock":
        stock = _parse_decimal(text)
        if stock is None or stock < 0:
            await update.message.reply_text(
                "Quantidade inválida. Informe um número igual ou maior que zero."
            )
            return

        pending.stock = stock
        pending.phase = "daily_use"
        await update.message.reply_text(
            f"Quanto de {pending.item} você consome por dia? "
            "Use a mesma unidade da quantidade em estoque."
        )
        return

    if pending.phase == "daily_use":
        daily_use = _parse_decimal(text)
        if daily_use is None or daily_use <= 0:
            await update.message.reply_text(
                "Consumo inválido. Informe um número maior que zero."
            )
            return

        pending.daily_use = daily_use
        pending.phase = "days_until_shop"
        await update.message.reply_text(
            "Em quantos dias será sua próxima compra? Informe um número inteiro maior que zero."
        )
        return

    if pending.phase == "days_until_shop":
        days_until_shop = _parse_days(text)
        if days_until_shop is None:
            await update.message.reply_text(
                "Prazo inválido. Informe em quantos dias será a próxima compra "
                "usando um número inteiro maior que zero."
            )
            return

        pending.days_until_shop = days_until_shop
        forecast = forecast_stock(
            stock=pending.stock,
            daily_use=pending.daily_use,
            days_until_shop=days_until_shop,
        )
        if forecast.shortage == 0:
            del context.user_data[PENDING_ANALYSIS_KEY]
            await update.message.reply_text(
                _format_forecast(pending, forecast)
                + "\nSeu estoque deve durar até a próxima compra; não precisa adicionar."
            )
            return

        pending.shortage = forecast.shortage
        pending.phase = "confirm"
        await update.message.reply_text(
            _format_forecast(pending, forecast)
            + f"\nQuer adicionar {_format_quantity(forecast.shortage)} "
            f"à lista de compras? Responda Sim ou Não."
        )
        return

    answer = _normalize_answer(text)
    if answer not in {"sim", "s", "não", "nao", "n"}:
        await update.message.reply_text(
            "Responda Sim para adicionar a quantidade faltante à lista "
            "ou Não para não adicionar."
        )
        return

    del context.user_data[PENDING_ANALYSIS_KEY]
    if answer in {"não", "nao", "n"}:
        await update.message.reply_text(
            f"Não adicionei {pending.item} à lista."
        )
        return

    if pending.shortage is None:
        raise RuntimeError("Análise pendente sem quantidade faltante.")

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    store: ShoppingListStore = context.bot_data[SHOPPING_STORE_KEY]
    total_quantity = store.add_quantity(user.id, pending.item, pending.shortage)

    await update.message.reply_text(
        f"Adicionei {pending.item} à lista. Quantidade acumulada: "
        f"{_format_quantity(total_quantity)}."
    )


async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    store: ShoppingListStore = context.bot_data[SHOPPING_STORE_KEY]
    shopping_list = store.get_items(user.id)
    if not shopping_list:
        await update.message.reply_text("Sua lista de compras está vazia.")
        return

    items = "\n".join(
        f"- {item.name}: {_format_quantity(item.quantity)}"
        for item in shopping_list
        if isinstance(item, ShoppingListItem)
    )
    if not items:
        await update.message.reply_text("Sua lista de compras está vazia.")
        return

    await update.message.reply_text(f"Itens para comprar:\n{items}")


async def mark_item_purchased(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Use /comprado <item> <quantidade>. "
            "Exemplo: /comprado tomates 2"
        )
        return

    item_name = " ".join(args[:-1]).strip()
    quantity = _parse_decimal(args[-1])
    if quantity is None or quantity <= 0:
        await update.message.reply_text(
            "Quantidade inválida. Informe um número maior que zero "
            "(por exemplo, 2 ou 0,5)."
        )
        return

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    store: ShoppingListStore = context.bot_data[SHOPPING_STORE_KEY]
    try:
        remaining_quantity = store.mark_purchased(
            user.id,
            item_name,
            quantity,
        )
    except InsufficientListedQuantity:
        await update.message.reply_text(
            f"Não é possível marcar {_format_quantity(quantity)} de {item_name} "
            "como comprado: a quantidade excede o que está na lista."
        )
        return

    if remaining_quantity is None:
        await update.message.reply_text(
            f"{item_name} não está na sua lista de compras."
        )
        return
    if remaining_quantity == 0:
        await update.message.reply_text(
            f"Marquei {item_name} como comprado e removi da lista."
        )
        return

    await update.message.reply_text(
        f"Marquei {_format_quantity(quantity)} de {item_name} como comprado. "
        f"Restam {_format_quantity(remaining_quantity)} na lista."
    )


async def cancel_item_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    pending = context.user_data.pop(PENDING_ANALYSIS_KEY, None)
    if not isinstance(pending, PendingAnalysis):
        await update.message.reply_text("Não há nenhuma análise em andamento.")
        return

    await update.message.reply_text(f"A análise de {pending.item} foi cancelada.")


def _parse_decimal(value: str) -> Decimal | None:
    try:
        number = Decimal(value.replace(",", "."))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _parse_item_quantity_unit(
    args: list[str],
) -> tuple[str, Decimal | None, str] | None:
    if len(args) < 3:
        return None
    item_name = " ".join(args[:-2]).strip()
    quantity = _parse_decimal(args[-2])
    unit = args[-1].strip()
    if not item_name or not unit:
        return None
    return item_name, quantity, unit


def _valid_pantry_name(item_name: str) -> bool:
    return (
        0 < len(item_name.strip()) <= 100
        and not any(ord(character) < 32 for character in item_name)
    )


def _valid_pantry_unit(unit: str) -> bool:
    return (
        0 < len(unit.strip()) <= 20
        and all(
            character.isalnum() or character in "._-"
            for character in unit.strip()
        )
    )


def _parse_days(value: str) -> int | None:
    try:
        days = int(value)
    except ValueError:
        return None
    return days if days > 0 else None


def _format_forecast(
    pending: PendingAnalysis,
    forecast: StockForecast,
) -> str:
    if (
        pending.stock is None
        or pending.daily_use is None
        or pending.days_until_shop is None
    ):
        raise RuntimeError("Análise incompleta ao montar a previsão.")

    details = (
        f"Análise de {pending.item}:\n"
        f"- Estoque atual: {_format_quantity(pending.stock)}\n"
        f"- Consumo: {_format_quantity(pending.daily_use)} por dia\n"
        f"- Próxima compra: em {pending.days_until_shop} dias"
    )
    if forecast.shortage == 0:
        return (
            f"{details}\n- Previsão: estoque suficiente; "
            f"sobram {_format_quantity(forecast.remaining)}."
        )

    if forecast.days_of_stock == 0:
        depletion = "Você já está sem estoque."
    else:
        depletion = (
            "O estoque acaba em aproximadamente "
            f"{_format_quantity(forecast.days_of_stock)} dias."
        )

    return (
        f"{details}\n- Previsão: {depletion} "
        f"Faltam {_format_quantity(forecast.shortage)} para cobrir o período."
    )


def _format_quantity(quantity: Decimal) -> str:
    return format(quantity.normalize(), "f")


def _normalize_answer(answer: str) -> str:
    normalized = unicodedata.normalize("NFD", answer.strip().casefold())
    return "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    )
