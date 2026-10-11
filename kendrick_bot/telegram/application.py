from telegram.ext import Application, CommandHandler

from kendrick_bot.config import Settings
from kendrick_bot.telegram.handlers import start


def build_application(settings: Settings) -> Application:
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", start))
    return application
