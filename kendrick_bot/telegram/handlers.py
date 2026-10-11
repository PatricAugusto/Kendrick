import unicodedata

from telegram import Update
from telegram.ext import ContextTypes

PENDING_ITEM_KEY = "pending_shopping_item"
SHOPPING_LIST_KEY = "shopping_list"


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "Olá! Envie o nome de um item para avaliarmos se precisa entrar na lista. "
        "Vou perguntar se seu estoque atual dura até a próxima compra. "
        "Use /lista para consultar os itens ou /cancelar para interromper uma avaliação."
    )


async def check_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.text is None:
        return

    item = update.message.text.strip()
    if not item:
        await update.message.reply_text("Envie o nome de um item para avaliar.")
        return

    context.user_data[PENDING_ITEM_KEY] = item
    await update.message.reply_text(
        f"Vamos avaliar {item}: o que você tem em casa dura até a próxima compra? "
        "Responda Sim ou Não."
    )


async def answer_item_check(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None or update.message.text is None:
        return

    item = context.user_data.get(PENDING_ITEM_KEY)
    if item is None:
        await check_item(update, context)
        return

    answer = _normalize_answer(update.message.text)
    if answer not in {"sim", "s", "não", "nao", "n"}:
        await update.message.reply_text(
            "Não entendi. Responda Sim se o estoque dura até a próxima compra "
            "ou Não se não dura."
        )
        return

    del context.user_data[PENDING_ITEM_KEY]

    if answer in {"sim", "s"}:
        await update.message.reply_text(
            f"Seu estoque de {item} dura até a próxima compra; não adicionei à lista."
        )
        return

    shopping_list = context.user_data.setdefault(SHOPPING_LIST_KEY, [])
    if any(existing.casefold() == item.casefold() for existing in shopping_list):
        await update.message.reply_text(f"{item} já está na lista de compras.")
        return

    shopping_list.append(item)
    await update.message.reply_text(f"Como o estoque não dura, adicionei {item} à lista.")


async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    shopping_list = context.user_data.get(SHOPPING_LIST_KEY, [])
    if not shopping_list:
        await update.message.reply_text("Sua lista de compras está vazia.")
        return

    items = "\n".join(f"- {item}" for item in shopping_list)
    await update.message.reply_text(f"Itens para comprar:\n{items}")


async def cancel_item_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    item = context.user_data.pop(PENDING_ITEM_KEY, None)
    if item is None:
        await update.message.reply_text("Não há nenhuma avaliação em andamento.")
        return

    await update.message.reply_text(f"A avaliação de {item} foi cancelada.")


def _normalize_answer(answer: str) -> str:
    normalized = unicodedata.normalize("NFD", answer.strip().casefold())
    return "".join(character for character in normalized if unicodedata.category(character) != "Mn")
