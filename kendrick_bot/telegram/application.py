from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from kendrick_bot.config import Settings
from kendrick_bot.llm.ollama import OllamaClient
from kendrick_bot.shopping.list_store import ShoppingListStore
from kendrick_bot.shopping.pantry_store import PantryStore
from kendrick_bot.telegram.handlers import (
    AUTHORIZED_USER_IDS_KEY,
    OLLAMA_CLIENT_KEY,
    PANTRY_STORE_KEY,
    SHOPPING_STORE_KEY,
    ask_assistant,
    answer_item_check,
    cancel_item_check,
    mark_item_purchased,
    plan_purchases,
    remove_pantry_item,
    set_pantry_consumption,
    set_pantry_stock,
    show_purchase_history,
    show_help,
    show_list,
    show_pantry,
    handle_confirmation_callback,
    start,
)


def build_application(settings: Settings) -> Application:
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data[SHOPPING_STORE_KEY] = ShoppingListStore()
    application.bot_data[PANTRY_STORE_KEY] = PantryStore()
    application.bot_data[OLLAMA_CLIENT_KEY] = OllamaClient(
        settings.ollama_base_url,
        settings.ollama_model,
    )
    application.bot_data[AUTHORIZED_USER_IDS_KEY] = settings.allowed_user_ids
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
        CommandHandler("despensa", show_pantry, filters=authorized_user)
    )
    application.add_handler(
        CommandHandler("estoque", set_pantry_stock, filters=authorized_user)
    )
    application.add_handler(
        CommandHandler("consumo", set_pantry_consumption, filters=authorized_user)
    )
    application.add_handler(
        CommandHandler(
            "remover_despensa",
            remove_pantry_item,
            filters=authorized_user,
        )
    )
    application.add_handler(
        CommandHandler("comprado", mark_item_purchased, filters=authorized_user)
    )
    application.add_handler(
        CommandHandler("planejar", plan_purchases, filters=authorized_user)
    )
    application.add_handler(
        CommandHandler("historico", show_purchase_history, filters=authorized_user)
    )
    application.add_handler(
        CommandHandler("cancelar", cancel_item_check, filters=authorized_user)
    )
    application.add_handler(
        CallbackQueryHandler(
            handle_confirmation_callback,
            pattern=r"^(plan|analysis):(yes|no)$",
        )
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
