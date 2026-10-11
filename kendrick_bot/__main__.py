import logging

from kendrick_bot.config import get_settings
from kendrick_bot.telegram.application import build_application


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    logger = logging.getLogger(__name__)

    settings = get_settings()
    application = build_application(settings)

    logger.info("Bot iniciado. Aguardando mensagens no Telegram...")
    application.run_polling()


if __name__ == "__main__":
    main()
