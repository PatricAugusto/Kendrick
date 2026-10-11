import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from telegram import Update
from telegram.ext import ContextTypes

from kendrick_bot.shopping.forecast import StockForecast, forecast_stock
from kendrick_bot.shopping.list_store import ShoppingListItem, ShoppingListStore

PENDING_ANALYSIS_KEY = "pending_stock_analysis"
SHOPPING_STORE_KEY = "shopping_list_store"


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
        "Comandos disponíveis:\n"
        "/start — ver esta mensagem de ajuda.\n"
        "/lista — consultar os itens e as quantidades para comprar.\n"
        "/cancelar — interromper a análise em andamento.\n\n"
        "Para começar, envie o nome de um item. Vou perguntar a quantidade "
        "em estoque, o consumo diário e em quantos dias será a próxima compra."
    )


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
