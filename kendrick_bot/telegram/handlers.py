from telegram import Update
from telegram.ext import ContextTypes


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "Olá! Sou seu assistente de compras. "
        "Por enquanto estou aprendendo a conversar; em breve vamos montar sua lista."
    )
