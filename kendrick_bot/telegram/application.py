from telegram.ext import Application, CommandHandler, MessageHandler, filters

from kendrick_bot.config import Settings
from kendrick_bot.telegram.handlers import (
    answer_item_check,
    cancel_item_check,
    show_list,
    start,
)


def build_application(settings: Settings) -> Application:
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("lista", show_list))
    application.add_handler(CommandHandler("cancelar", cancel_item_check))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, answer_item_check)
    )
    return application
