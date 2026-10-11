import unicodedata
from dataclasses import dataclass
from datetime import timezone
from decimal import Decimal, InvalidOperation
from typing import Literal

from telegram import (
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
)
from telegram.ext import ContextTypes

from kendrick_bot.llm.ollama import OllamaClient, OllamaError
from kendrick_bot.shopping.forecast import StockForecast, forecast_stock
from kendrick_bot.shopping.pantry_store import (
    PantryInvalidQuantity,
    PantryItemNotFound,
    PantryStore,
    PantryUnitMismatch,
)
from kendrick_bot.shopping.list_store import (
    InsufficientListedQuantity,
    ShoppingListUnitMismatch,
    ShoppingListItem,
    ShoppingListStore,
)

PENDING_ANALYSIS_KEY = "pending_stock_analysis"
SHOPPING_STORE_KEY = "shopping_list_store"
OLLAMA_CLIENT_KEY = "ollama_client"
PANTRY_STORE_KEY = "pantry_store"
PENDING_PLAN_KEY = "pending_purchase_plan"
AUTHORIZED_USER_IDS_KEY = "authorized_user_ids"
HELP_TEXT = (
    "Como posso ajudar?\n\n"
    "🧺 DESPENSA\n"
    "/despensa — ver seus itens e estoques.\n"
    "/estoque <item> <quantidade> <unidade> — atualizar estoque.\n"
    "/consumo <item> <quantidade> <unidade>/dia — definir consumo.\n"
    "/remover_despensa <item> confirmar — remover um item.\n\n"
    "🛒 COMPRAS\n"
    "/planejar <dias> — prever o que pode faltar.\n"
    "/lista — ver sua lista de compras.\n"
    "/comprado <item> <quantidade> — registrar uma compra.\n"
    "/historico [dias] — consultar compras (padrão: 30 dias).\n\n"
    "💬 AJUDA\n"
    "/start — abrir esta apresentação.\n"
    "/ajuda — consultar os comandos novamente.\n"
    "/perguntar <dúvida> — pedir uma sugestão.\n"
    "/cancelar — interromper o fluxo atual.\n\n"
    "Dica: envie o nome de um item para iniciar uma análise de estoque. "
    "Use /consumo para cadastrar o consumo diário e mantenha a mesma unidade "
    "no estoque e no consumo (por exemplo, kg). "
    "Sugestões de planejamento só entram na lista com sua confirmação."
)


@dataclass
class PendingAnalysis:
    item: str
    phase: Literal["stock", "daily_use", "days_until_shop", "confirm"] = "stock"
    stock: Decimal | None = None
    daily_use: Decimal | None = None
    days_until_shop: int | None = None
    shortage: Decimal | None = None


@dataclass(frozen=True)
class PlannedShortage:
    name: str
    quantity: Decimal
    unit: str


@dataclass(frozen=True)
class PendingPurchasePlan:
    days: int
    shortages: tuple[PlannedShortage, ...]


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "Oi! Sou o Kendrick 👋\n"
        "Vamos deixar suas compras mais simples.\n\n"
        + HELP_TEXT
    )


async def show_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    await update.message.reply_text(HELP_TEXT)


async def show_pantry(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    store: PantryStore = context.bot_data[PANTRY_STORE_KEY]
    pantry_items = store.get_items(user.id)
    if not pantry_items:
        await update.message.reply_text(
            "Sua despensa ainda não tem itens cadastrados. "
            "Use /estoque <item> <quantidade> <unidade> para começar."
        )
        return

    lines = []
    for item in pantry_items:
        consumption = (
            f"{_format_quantity(item.daily_consumption)} {item.unit}/dia"
            if item.daily_consumption is not None
            else "consumo não informado"
        )
        lines.append(
            f"- {item.name}: {_format_quantity(item.quantity)} "
            f"{item.unit}; consumo: {consumption}"
        )
    await update.message.reply_text(
        "🧺 Sua despensa\n\n" + "\n".join(lines)
    )


async def plan_purchases(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    if len(context.args) != 1:
        await update.message.reply_text(
            "Use /planejar <dias>. Exemplo: /planejar 7 "
            "(período entre 1 e 365 dias)."
        )
        return
    days = _parse_days(context.args[0])
    if days is None or days > 365:
        await update.message.reply_text(
            "Informe um período inteiro entre 1 e 365 dias."
        )
        return

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    pantry: PantryStore = context.bot_data[PANTRY_STORE_KEY]
    pantry_items = pantry.get_items(user.id)
    if not pantry_items:
        await update.message.reply_text(
            "Sua despensa está vazia. Cadastre itens com /estoque antes de planejar."
        )
        return
    if isinstance(context.user_data.get(PENDING_ANALYSIS_KEY), PendingAnalysis):
        await update.message.reply_text(
            "Há uma análise de estoque em andamento. Use /cancelar antes de iniciar "
            "um planejamento."
        )
        return

    shortages: list[PlannedShortage] = []
    sufficient_items: list[str] = []
    items_without_consumption: list[str] = []
    for item in pantry_items:
        if item.daily_consumption is None:
            items_without_consumption.append(item.name)
            continue
        forecast = forecast_stock(
            stock=item.quantity,
            daily_use=item.daily_consumption,
            days_until_shop=days,
        )
        if forecast.shortage > 0:
            shortages.append(
                PlannedShortage(item.name, forecast.shortage, item.unit)
            )
        else:
            sufficient_items.append(item.name)

    lines = [f"🗓 Compras para os próximos {days} dias"]
    if shortages:
        lines.append("\n🔸 Pode faltar")
    lines.extend(
        f"• {shortage.name} — {_format_quantity(shortage.quantity)} "
        f"{shortage.unit}"
        for shortage in shortages
    )
    if sufficient_items:
        lines.append("\n✅ Estoque suficiente")
        lines.extend(f"• {name}" for name in sufficient_items)
    if items_without_consumption:
        lines.append(
            "\nℹ️ Sem consumo cadastrado: "
            + ", ".join(items_without_consumption)
            + ". Defina com /consumo."
        )

    if not shortages:
        if sufficient_items:
            lines.append("\nTudo certo — não precisa repor nada agora.")
        context.user_data.pop(PENDING_PLAN_KEY, None)
        await update.message.reply_text("\n".join(lines))
        return

    context.user_data[PENDING_PLAN_KEY] = PendingPurchasePlan(
        days=days,
        shortages=tuple(shortages),
    )
    lines.append("\nAdicionar essas quantidades à sua lista?")
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=_yes_no_keyboard("plan"),
    )


async def handle_confirmation_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if query is None:
        return

    authorized_user_ids: frozenset[int] = context.bot_data[
        AUTHORIZED_USER_IDS_KEY
    ]
    if (
        query.from_user.id not in authorized_user_ids
        or query.message is None
        or query.message.chat.type != Chat.PRIVATE
    ):
        await query.answer("Acesso não autorizado.", show_alert=True)
        return
    if not isinstance(query.message, Message):
        await query.answer("Não consegui acessar esta confirmação.", show_alert=True)
        return

    if query.data in {"plan:yes", "plan:no"}:
        pending_plan = context.user_data.get(PENDING_PLAN_KEY)
        if not isinstance(pending_plan, PendingPurchasePlan):
            await query.answer("Essa confirmação não está mais ativa.", show_alert=True)
            return
        await query.answer()
        await _answer_purchase_plan(
            query.message,
            context,
            "sim" if query.data == "plan:yes" else "não",
            pending_plan,
            query.from_user.id,
        )
        return

    if query.data in {"analysis:yes", "analysis:no"}:
        pending_analysis = context.user_data.get(PENDING_ANALYSIS_KEY)
        if (
            not isinstance(pending_analysis, PendingAnalysis)
            or pending_analysis.phase != "confirm"
        ):
            await query.answer("Essa confirmação não está mais ativa.", show_alert=True)
            return
        await query.answer()
        await _answer_analysis_confirmation(
            query.message,
            context,
            "sim" if query.data == "analysis:yes" else "não",
            pending_analysis,
            query.from_user.id,
        )
        return

    await query.answer("Essa confirmação não está mais ativa.", show_alert=True)


async def show_purchase_history(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    args = context.args
    if len(args) > 1:
        await update.message.reply_text(
            "Use /historico [dias], por exemplo /historico 30."
        )
        return
    days = 30 if not args else _parse_days(args[0])
    if days is None or days > 365:
        await update.message.reply_text(
            "Informe um período inteiro entre 1 e 365 dias."
        )
        return

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    store: ShoppingListStore = context.bot_data[SHOPPING_STORE_KEY]
    records = store.get_history(user.id, days)
    if not records:
        await update.message.reply_text(
            f"🧾 Nenhuma compra marcada nos últimos {days} dias."
        )
        return

    lines = [
        f"{record.purchased_at.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} — "
        f"{record.name}: {_format_quantity(record.quantity)}"
        + (f" {record.unit}" if record.unit else "")
        for record in records
    ]
    suffix = (
        "\nMostrando até as 20 compras mais recentes."
        if len(records) == 20
        else ""
    )
    await update.message.reply_text(
        f"🧾 Compras dos últimos {days} dias\n\n"
        + "\n".join(f"- {line}" for line in lines)
        + suffix
    )


async def set_pantry_stock(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    parsed = _parse_item_quantity_unit(context.args)
    if parsed is None:
        await update.message.reply_text(
            "Use /estoque <item> <quantidade> <unidade>. "
            "Exemplo: /estoque arroz 2 kg"
        )
        return
    item_name, quantity, unit = parsed
    if (
        not _valid_pantry_name(item_name)
        or not _valid_pantry_unit(unit)
        or quantity is None
        or quantity < 0
    ):
        await update.message.reply_text(
            "Item, unidade ou quantidade inválidos. Informe um estoque maior "
            "ou igual a zero e uma unidade como kg, L ou unidades."
        )
        return

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    store: PantryStore = context.bot_data[PANTRY_STORE_KEY]
    try:
        item = store.set_stock(user.id, item_name, quantity, unit)
    except PantryInvalidQuantity:
        await update.message.reply_text(
            "Quantidade inválida. Use um número entre zero e "
            "999999999999, com no máximo seis casas decimais."
        )
        return
    except PantryUnitMismatch:
        await update.message.reply_text(
            f"{item_name} já está cadastrado com outra unidade. "
            "Remova-o da despensa e cadastre novamente para trocar a unidade."
        )
        return

    await update.message.reply_text(
        f"Estoque de {item.name} atualizado: "
        f"{_format_quantity(item.quantity)} {item.unit}."
    )


async def set_pantry_consumption(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    parsed = _parse_item_quantity_unit(context.args)
    if parsed is None:
        await update.message.reply_text(
            "Use /consumo <item> <quantidade> <unidade>/dia. "
            "Exemplo: /consumo arroz 0,1 kg/dia"
        )
        return
    item_name, quantity, raw_unit = parsed
    if not _valid_pantry_name(item_name) or quantity is None or quantity <= 0:
        await update.message.reply_text(
            "Item, unidade ou consumo inválidos. Informe um consumo diário "
            "maior que zero, como 0,1 kg/dia."
        )
        return
    if not raw_unit.casefold().endswith("/dia"):
        await update.message.reply_text(
            "Informe o consumo por dia, por exemplo: "
            "/consumo arroz 0,1 kg/dia"
        )
        return

    unit = raw_unit[:-4]
    if not _valid_pantry_unit(unit):
        await update.message.reply_text(
            "Unidade inválida. Use uma unidade como kg, L ou unidades."
        )
        return

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    store: PantryStore = context.bot_data[PANTRY_STORE_KEY]
    try:
        item = store.set_daily_consumption(user.id, item_name, quantity, unit)
    except PantryInvalidQuantity:
        await update.message.reply_text(
            "Consumo inválido. Use um número maior que zero e menor que "
            "1000000000000, com no máximo seis casas decimais."
        )
        return
    except PantryItemNotFound:
        await update.message.reply_text(
            f"{item_name} ainda não está na despensa. Cadastre primeiro com "
            "/estoque <item> <quantidade> <unidade>."
        )
        return
    except PantryUnitMismatch:
        await update.message.reply_text(
            f"A unidade de consumo de {item_name} deve ser igual à unidade "
            "cadastrada no estoque."
        )
        return

    await update.message.reply_text(
        f"Consumo diário de {item.name} atualizado: "
        f"{_format_quantity(quantity)} {item.unit}/dia."
    )


async def remove_pantry_item(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    args = context.args
    if len(args) < 2 or args[-1].casefold() != "confirmar":
        await update.message.reply_text(
            "Para confirmar a remoção, use /remover_despensa <item> confirmar. "
            "Exemplo: /remover_despensa arroz confirmar"
        )
        return
    item_name = " ".join(args[:-1]).strip()
    if not _valid_pantry_name(item_name):
        await update.message.reply_text(
            "Informe o nome do item. Exemplo: /remover_despensa arroz confirmar"
        )
        return

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    store: PantryStore = context.bot_data[PANTRY_STORE_KEY]
    if not store.remove_item(user.id, item_name):
        await update.message.reply_text(
            f"{item_name} não está cadastrado na sua despensa."
        )
        return
    await update.message.reply_text(
        f"Removi {item_name} da despensa. Isso não altera sua lista de compras."
    )


async def ask_assistant(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    question = " ".join(context.args).strip()
    if not question:
        await update.message.reply_text(
            "Escreva sua dúvida depois do comando. "
            "Exemplo: /perguntar como organizar as compras da semana?"
        )
        return

    client: OllamaClient = context.bot_data[OLLAMA_CLIENT_KEY]
    try:
        answer = await client.ask(question)
    except OllamaError:
        await update.message.reply_text(
            "Não consegui obter uma resposta do modelo local. Confira se o "
            "Ollama está aberto e se o modelo configurado está instalado."
        )
        return

    await update.message.reply_text(answer)


async def answer_item_check(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None or update.message.text is None:
        return

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Envie o nome de um item para analisar.")
        return

    pending_plan = context.user_data.get(PENDING_PLAN_KEY)
    if isinstance(pending_plan, PendingPurchasePlan):
        user = update.effective_user
        if user is None:
            raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
        await _answer_purchase_plan(
            update.message,
            context,
            text,
            pending_plan,
            user.id,
        )
        return

    pending = context.user_data.get(PENDING_ANALYSIS_KEY)
    if not isinstance(pending, PendingAnalysis):
        context.user_data[PENDING_ANALYSIS_KEY] = PendingAnalysis(item=text)
        await update.message.reply_text(
            f"Vamos analisar {text}. Quanto você tem em estoque? "
            "Envie apenas a quantidade (por exemplo, 3). Use a mesma unidade "
            "para as próximas quantidades, como unidades ou kg."
        )
        return

    if pending.phase == "stock":
        stock = _parse_decimal(text)
        if stock is None or stock < 0:
            await update.message.reply_text(
                "Quantidade inválida. Informe um número igual ou maior que zero."
            )
            return

        pending.stock = stock
        pending.phase = "daily_use"
        await update.message.reply_text(
            f"Quanto de {pending.item} você consome por dia? "
            "Use a mesma unidade da quantidade em estoque."
        )
        return

    if pending.phase == "daily_use":
        daily_use = _parse_decimal(text)
        if daily_use is None or daily_use <= 0:
            await update.message.reply_text(
                "Consumo inválido. Informe um número maior que zero."
            )
            return

        pending.daily_use = daily_use
        pending.phase = "days_until_shop"
        await update.message.reply_text(
            "Em quantos dias será sua próxima compra? Informe um número inteiro maior que zero."
        )
        return

    if pending.phase == "days_until_shop":
        days_until_shop = _parse_days(text)
        if days_until_shop is None:
            await update.message.reply_text(
                "Prazo inválido. Informe em quantos dias será a próxima compra "
                "usando um número inteiro maior que zero."
            )
            return

        pending.days_until_shop = days_until_shop
        forecast = forecast_stock(
            stock=pending.stock,
            daily_use=pending.daily_use,
            days_until_shop=days_until_shop,
        )
        if forecast.shortage == 0:
            del context.user_data[PENDING_ANALYSIS_KEY]
            await update.message.reply_text(
                _format_forecast(pending, forecast)
                + "\nSeu estoque deve durar até a próxima compra; não precisa adicionar."
            )
            return

        pending.shortage = forecast.shortage
        pending.phase = "confirm"
        await update.message.reply_text(
            _format_forecast(pending, forecast)
            + f"\n\nAdicionar {_format_quantity(forecast.shortage)} "
            "à sua lista?",
            reply_markup=_yes_no_keyboard("analysis"),
        )
        return

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    await _answer_analysis_confirmation(
        update.message,
        context,
        text,
        pending,
        user.id,
    )


async def _answer_analysis_confirmation(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    answer_text: str,
    pending: PendingAnalysis,
    user_id: int,
) -> None:
    answer = _normalize_answer(answer_text)
    if answer not in {"sim", "s", "não", "nao", "n"}:
        await message.reply_text(
            "Escolha Sim para adicionar o item à lista ou Não para manter "
            "a lista como está."
        )
        return

    context.user_data.pop(PENDING_ANALYSIS_KEY, None)
    if answer in {"não", "nao", "n"}:
        await message.reply_text(
            f"Tudo certo — não adicionei {pending.item} à lista."
        )
        return
    if pending.shortage is None:
        raise RuntimeError("Análise pendente sem quantidade faltante.")

    store: ShoppingListStore = context.bot_data[SHOPPING_STORE_KEY]
    total_quantity = store.add_quantity(user_id, pending.item, pending.shortage)
    await message.reply_text(
        f"✅ {pending.item} adicionado à lista\n"
        f"Quantidade acumulada: {_format_quantity(total_quantity)}."
    )


async def _answer_purchase_plan(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    answer_text: str,
    pending: PendingPurchasePlan,
    user_id: int,
) -> None:
    answer = _normalize_answer(answer_text)
    if answer not in {"sim", "s", "não", "nao", "n"}:
        await message.reply_text(
            "Responda Sim para adicionar as sugestões à lista ou Não para manter "
            "a lista como está."
        )
        return

    context.user_data.pop(PENDING_PLAN_KEY, None)
    if answer in {"não", "nao", "n"}:
        await message.reply_text(
            "Tudo certo — mantive sua lista como estava."
        )
        return

    store: ShoppingListStore = context.bot_data[SHOPPING_STORE_KEY]
    additions = [
        (item.name, item.quantity, item.unit)
        for item in pending.shortages
    ]
    try:
        totals = store.add_quantities(user_id, additions)
    except ShoppingListUnitMismatch:
        await message.reply_text(
            "Não alterei a lista: um item já está cadastrado com outra unidade. "
            "Confira a lista e a despensa antes de tentar novamente."
        )
        return
    except ValueError:
        await message.reply_text(
            "Não alterei a lista: uma quantidade acumulada excede o limite. "
            "Revise os dados e tente novamente."
        )
        return

    details = "\n".join(
        f"- {item.name}: {_format_quantity(total)} {item.unit}"
        for item, total in zip(pending.shortages, totals, strict=True)
    )
    await message.reply_text(
        f"✅ Adicionado à sua lista\n\n{details}"
    )


def _yes_no_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Sim, adicionar",
                    callback_data=f"{action}:yes",
                ),
                InlineKeyboardButton(
                    "Não, obrigado",
                    callback_data=f"{action}:no",
                ),
            ]
        ]
    )


async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    store: ShoppingListStore = context.bot_data[SHOPPING_STORE_KEY]
    shopping_list = store.get_items(user.id)
    if not shopping_list:
        await update.message.reply_text(
            "🛒 Sua lista está vazia.\n\n"
            "Envie o nome de um item para começar uma análise."
        )
        return

    items = "\n".join(
        f"- {item.name}: {_format_quantity(item.quantity)}"
        + (f" {item.unit}" if item.unit else "")
        for item in shopping_list
        if isinstance(item, ShoppingListItem)
    )
    if not items:
        await update.message.reply_text("🛒 Sua lista está vazia.")
        return

    await update.message.reply_text(f"🛒 Sua lista de compras\n\n{items}")


async def mark_item_purchased(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Use /comprado <item> <quantidade>. "
            "Exemplo: /comprado tomates 2"
        )
        return

    item_name = " ".join(args[:-1]).strip()
    quantity = _parse_decimal(args[-1])
    if quantity is None or quantity <= 0:
        await update.message.reply_text(
            "Quantidade inválida. Informe um número maior que zero "
            "(por exemplo, 2 ou 0,5)."
        )
        return

    user = update.effective_user
    if user is None:
        raise RuntimeError("Não foi possível identificar o usuário da mensagem.")
    store: ShoppingListStore = context.bot_data[SHOPPING_STORE_KEY]
    try:
        remaining_quantity = store.mark_purchased(
            user.id,
            item_name,
            quantity,
        )
    except InsufficientListedQuantity:
        await update.message.reply_text(
            f"Não é possível marcar {_format_quantity(quantity)} de {item_name} "
            "como comprado: a quantidade excede o que está na lista."
        )
        return
    except ValueError:
        await update.message.reply_text(
            "Quantidade inválida ou fora do limite permitido."
        )
        return

    if remaining_quantity is None:
        await update.message.reply_text(
            f"{item_name} não está na sua lista de compras."
        )
        return
    if remaining_quantity == 0:
        await update.message.reply_text(
            f"Marquei {item_name} como comprado e removi da lista."
        )
        return

    await update.message.reply_text(
        f"Marquei {_format_quantity(quantity)} de {item_name} como comprado. "
        f"Restam {_format_quantity(remaining_quantity)} na lista."
    )


async def cancel_item_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    pending = context.user_data.pop(PENDING_ANALYSIS_KEY, None)
    pending_plan = context.user_data.pop(PENDING_PLAN_KEY, None)
    if isinstance(pending_plan, PendingPurchasePlan):
        await update.message.reply_text("O planejamento foi cancelado.")
        return
    if not isinstance(pending, PendingAnalysis):
        await update.message.reply_text("Não há nenhuma análise em andamento.")
        return

    await update.message.reply_text(f"A análise de {pending.item} foi cancelada.")


def _parse_decimal(value: str) -> Decimal | None:
    try:
        number = Decimal(value.replace(",", "."))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _parse_item_quantity_unit(
    args: list[str],
) -> tuple[str, Decimal | None, str] | None:
    if len(args) < 3:
        return None
    item_name = " ".join(args[:-2]).strip()
    quantity = _parse_decimal(args[-2])
    unit = args[-1].strip()
    if not item_name or not unit:
        return None
    return item_name, quantity, unit


def _valid_pantry_name(item_name: str) -> bool:
    return (
        0 < len(item_name.strip()) <= 100
        and not any(ord(character) < 32 for character in item_name)
    )


def _valid_pantry_unit(unit: str) -> bool:
    return (
        0 < len(unit.strip()) <= 20
        and all(
            character.isalnum() or character in "._-"
            for character in unit.strip()
        )
    )


def _parse_days(value: str) -> int | None:
    try:
        days = int(value)
    except ValueError:
        return None
    return days if days > 0 else None


def _format_forecast(
    pending: PendingAnalysis,
    forecast: StockForecast,
) -> str:
    if (
        pending.stock is None
        or pending.daily_use is None
        or pending.days_until_shop is None
    ):
        raise RuntimeError("Análise incompleta ao montar a previsão.")

    details = (
        f"Análise de {pending.item}:\n"
        f"- Estoque atual: {_format_quantity(pending.stock)}\n"
        f"- Consumo: {_format_quantity(pending.daily_use)} por dia\n"
        f"- Próxima compra: em {pending.days_until_shop} dias"
    )
    if forecast.shortage == 0:
        return (
            f"{details}\n- Previsão: estoque suficiente; "
            f"sobram {_format_quantity(forecast.remaining)}."
        )

    if forecast.days_of_stock == 0:
        depletion = "Você já está sem estoque."
    else:
        depletion = (
            "O estoque acaba em aproximadamente "
            f"{_format_quantity(forecast.days_of_stock)} dias."
        )

    return (
        f"{details}\n- Previsão: {depletion} "
        f"Faltam {_format_quantity(forecast.shortage)} para cobrir o período."
    )


def _format_quantity(quantity: Decimal) -> str:
    return format(quantity.normalize(), "f")


def _normalize_answer(answer: str) -> str:
    normalized = unicodedata.normalize("NFD", answer.strip().casefold())
    return "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    )
