import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "Olá! Sou seu assistente de compras. "
        "Por enquanto estou aprendendo a conversar; em breve vamos montar sua lista."
    )


def main() -> None:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Token do Telegram não configurado. "
            "Crie um arquivo .env com TELEGRAM_BOT_TOKEN=seu_token."
        )

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))

    logger.info("Bot iniciado. Aguardando mensagens no Telegram...")
    application.run_polling()


if __name__ == "__main__":
    main()
