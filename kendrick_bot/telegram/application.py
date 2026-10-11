from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from kendrick_bot.config import Settings
from kendrick_bot.llm.ollama import OllamaClient
from kendrick_bot.shopping.list_store import ShoppingListStore
from kendrick_bot.telegram.handlers import (
    OLLAMA_CLIENT_KEY,
    SHOPPING_STORE_KEY,
    ask_assistant,
    answer_item_check,
    cancel_item_check,
    mark_item_purchased,
    show_help,
    show_list,
    start,
)


def build_application(settings: Settings) -> Application:
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data[SHOPPING_STORE_KEY] = ShoppingListStore()
    application.bot_data[OLLAMA_CLIENT_KEY] = OllamaClient(
        settings.ollama_base_url,
        settings.ollama_model,
    )
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
        CommandHandler("ajuda", show_help, filters=authorized_user)
    )
    application.add_handler(
        CommandHandler("perguntar", ask_assistant, filters=authorized_user)
    )
    application.add_handler(
        CommandHandler("lista", show_list, filters=authorized_user)
    )
    application.add_handler(
        CommandHandler("comprado", mark_item_purchased, filters=authorized_user)
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
