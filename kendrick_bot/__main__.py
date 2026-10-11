import logging

import logging

from telegram.error import InvalidToken

from kendrick_bot.config import get_settings
from kendrick_bot.security import configure_logging
from kendrick_bot.telegram.application import build_application


def main() -> None:
    settings = get_settings()
    configure_logging(settings.telegram_bot_token)
    logger = logging.getLogger(__name__)
    application = build_application(settings)

    logger.info("Conectando ao Telegram...")
    try:
        application.run_polling()
    except InvalidToken:
        raise SystemExit(
            "O Telegram rejeitou o token. Confira TELEGRAM_BOT_TOKEN no .env; "
            "se ele foi exposto, revogue-o no @BotFather e configure um novo."
        ) from None


if __name__ == "__main__":
    main()
