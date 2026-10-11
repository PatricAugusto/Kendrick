from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from kendrick_bot.config import Settings
from kendrick_bot.telegram.handlers import (
    answer_item_check,
    cancel_item_check,
    show_list,
    start,
)


def build_application(settings: Settings) -> Application:
    application = Application.builder().token(settings.telegram_bot_token).build()
    authorized_user = filters.ChatType.PRIVATE & filters.User(
        user_id=settings.allowed_user_ids
    )
    application.add_handler(
        MessageHandler(
            filters.UpdateType.MESSAGE & ~authorized_user,
            reject_unauthorized_user,
        ),
        group=-1,
    )
    application.add_handler(CommandHandler("start", start, filters=authorized_user))
    application.add_handler(
        CommandHandler("lista", show_list, filters=authorized_user)
    )
    application.add_handler(
        CommandHandler("cancelar", cancel_item_check, filters=authorized_user)
    )
    application.add_handler(
        MessageHandler(
            authorized_user & filters.TEXT & ~filters.COMMAND,
            answer_item_check,
        )
    )
    return application


async def reject_unauthorized_user(
    update: Update,
    _: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is not None:
        await update.message.reply_text("Acesso não autorizado. Este bot é privado.")
