import logging
import os

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from invoice_parser import extract_pdf_text, parse_invoice
from invoice_ai import analyze_invoice
from invoice_reconciliation import reconcile_invoice

from keyboards.main_menu import main_menu


router = Router()
logger = logging.getLogger(__name__)


# ============================================================
# Тимчасове зберігання даних користувачів
# ============================================================

user_invoices = {}


# ============================================================
# Назви полів українською мовою
# ============================================================

FIELD_NAMES = {
    "document_type": "Тип документа",
    "document_number": "Номер документа",
    "date": "Дата",

    "supplier": "Отримувач",
    "supplier_address": "Адреса отримувача",

    "recipient": "Платник",
    "recipient_address": "Адреса платника",

    "payment_provider": "Платіжна система",

    "description": "Опис",
    "quantity": "Кількість",
    "unit_price": "Ціна",
    "vat": "ПДВ",
    "total": "Сума",
    "currency": "Валюта",

    "iban": "IBAN",
    "swift": "SWIFT",
    "bank": "Банк",
    "bank_address": "Адреса банку",
}


# ============================================================
# Формування повідомлення з даними інвойсу
# ============================================================

def build_invoice_text(data: dict) -> str:
    return (
        "📄 Інформація з інвойсу\n\n"

        f"Тип документа: {data.get('document_type', '')}\n"
        f"Номер: {data.get('document_number', '')}\n"
        f"Дата: {data.get('date', '')}\n\n"

        f"Отримувач: {data.get('supplier', '')}\n"
        f"Адреса отримувача: "
        f"{data.get('supplier_address', '')}\n\n"

        f"Платник: {data.get('recipient', '')}\n"
        f"Адреса платника: "
        f"{data.get('recipient_address', '')}\n\n"

        f"Платіжна система: "
        f"{data.get('payment_provider', '')}\n\n"

        f"Опис: {data.get('description', '')}\n"
        f"Кількість: {data.get('quantity', '')}\n"
        f"Ціна: {data.get('unit_price', '')}\n"
        f"ПДВ: {data.get('vat', '')}\n"
        f"Сума: {data.get('total', '')} "
        f"{data.get('currency', '')}\n\n"

        f"IBAN: {data.get('iban', '')}\n"
        f"SWIFT: {data.get('swift', '')}\n"
        f"Банк: {data.get('bank', '')}\n"
        f"Адреса банку: {data.get('bank_address', '')}\n\n"

        "⚠️ Будь ласка, перевірте всю інформацію "
        "перед використанням."
    )


# ============================================================
# Клавіатура підтвердження
# ============================================================

def confirmation_keyboard():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="✅ Все правильно",
        callback_data="invoice_confirm"
    )

    builder.button(
        text="✏️ Є помилка",
        callback_data="invoice_edit"
    )

    builder.adjust(2)

    return builder.as_markup()


# ============================================================
# Клавіатура вибору поля для редагування
# ============================================================

def edit_fields_keyboard():
    builder = InlineKeyboardBuilder()

    for field_key, field_name in FIELD_NAMES.items():
        builder.button(
            text=field_name,
            callback_data=f"edit_field:{field_key}"
        )

    builder.adjust(2)

    return builder.as_markup()


# ============================================================
# /start
# ============================================================

@router.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Привіт! Я бот для читання інвойсів.\n"
        "Обери дію:",
        reply_markup=main_menu,
    )


# ============================================================
# /help
# ============================================================

@router.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "Привіт! Я бот для читання інвойсів.\n"
        "Обери дію:",
        reply_markup=main_menu,
    )


# ============================================================
# Кнопка "📄 Інвойс"
# ============================================================

@router.message(F.text == "📄 Інвойс")
async def invoice_button_handler(message: Message):
    await message.answer(
        "Надішли мені інвойс у форматі PDF."
    )


# ============================================================
# Обробка PDF-документа
# ============================================================

@router.message(F.document)
async def invoice_document_handler(message: Message):
    document = message.document

    file_name = document.file_name or ""

    if not file_name.lower().endswith(".pdf"):
        await message.answer(
            "Будь ласка, надішли інвойс у форматі PDF."
        )
        return

    os.makedirs("downloads", exist_ok=True)

    file_path = "downloads/invoice.pdf"

    try:
        # ----------------------------------------------------
        # 1. Зберігаємо PDF
        # ----------------------------------------------------

        await message.bot.download(
            document,
            destination=file_path
        )

        logger.info(
            "Invoice PDF saved for user %s.",
            message.from_user.id,
        )

        await message.answer(
            "Інвойс отримано.\n"
            "Починаю обробку..."
        )

        # ----------------------------------------------------
        # 2. Локальне вилучення тексту через pypdf
        # ----------------------------------------------------

        extracted_text = extract_pdf_text(
            file_path
        )

        logger.info(
            "PDF text extracted for user %s.",
            message.from_user.id,
        )

        # ----------------------------------------------------
        # 3. Локальний parser
        # ----------------------------------------------------

        local_result = parse_invoice(
            file_path
        )

        logger.info(
            "Local parser completed for user %s.",
            message.from_user.id,
        )

        # ----------------------------------------------------
        # 4. GPT
        # ----------------------------------------------------

        ai_result = analyze_invoice(
            pdf_path=file_path,
            extracted_text=extracted_text,
            parser_result=local_result,
        )

        logger.info(
            "GPT analysis completed for user %s.",
            message.from_user.id,
        )

        # ----------------------------------------------------
        # 5. Порівняння результатів
        # ----------------------------------------------------

        reconciliation_result = reconcile_invoice(
            local_result,
            ai_result
        )

        logger.info(
            "Reconciliation completed for user %s.",
            message.from_user.id,
        )

        final_data = reconciliation_result["data"]

        conflicts = reconciliation_result["conflicts"]

        # ----------------------------------------------------
        # Якщо є конфлікти
        # ----------------------------------------------------

        if conflicts:
            conflict_text = (
                "⚠️ Виявлено розбіжності.\n\n"
            )

            for field, values in conflicts.items():
                field_name = FIELD_NAMES.get(
                    field,
                    field
                )

                conflict_text += (
                    f"{field_name}:\n"
                    f"Parser: {values['parser']}\n"
                    f"GPT: {values['gpt']}\n\n"
                )

            conflict_text += (
                "Будь ласка, перевірте інформацію "
                "в оригінальному документі."
            )

            # ------------------------------------------------
            # Зберігаємо дані навіть при конфліктах.
            # Раніше тут був return до збереження user_invoices,
            # тому кнопка "Є помилка" не могла запустити
            # режим ручного виправлення.
            # ------------------------------------------------

            user_invoices[message.from_user.id] = {
                "data": final_data,
                "editing_field": None,
            }

            conflict_text += (
                "\n\n✏️ Натисніть «Є помилка», "
                "щоб вибрати поле та ввести правильне значення."
            )

            await message.answer(
                conflict_text,
                reply_markup=confirmation_keyboard()
            )

            return

        # ----------------------------------------------------
        # Зберігаємо результат користувача
        # ----------------------------------------------------

        user_invoices[message.from_user.id] = {
            "data": final_data,
            "editing_field": None,
        }

        # ----------------------------------------------------
        # Показуємо результат
        # ----------------------------------------------------

        await message.answer(
            build_invoice_text(final_data),
            reply_markup=confirmation_keyboard()
        )

    except Exception:
        logger.exception(
            "Invoice processing failed for user %s.",
            message.from_user.id,
        )

        await message.answer(
            "❌ Не вдалося обробити інвойс.\n\n"
            "Можливо, документ має погану якість "
            "або його неможливо коректно розпізнати."
        )


# ============================================================
# Обробка фотографії
# ============================================================

@router.message(F.photo)
async def invoice_photo_handler(message: Message):
    await message.answer(
        "Наразі обробка зображень ще не підключена.\n\n"
        "Будь ласка, надішли PDF-файл інвойсу."
    )


# ============================================================
# Кнопка "✅ Все правильно"
# ============================================================

@router.callback_query(F.data == "invoice_confirm")
async def invoice_confirm_handler(
    callback: CallbackQuery
):
    user_id = callback.from_user.id

    if user_id not in user_invoices:
        await callback.answer(
            "Дані інвойсу більше недоступні.",
            show_alert=True
        )
        return

    await callback.answer()

    await callback.message.answer(
        "✅ Дані інвойсу підтверджено."
    )

    logger.info(
        "Invoice confirmed by user %s.",
        user_id,
    )


# ============================================================
# Кнопка "✏️ Є помилка"
# ============================================================

@router.callback_query(F.data == "invoice_edit")
async def invoice_edit_handler(
    callback: CallbackQuery
):
    user_id = callback.from_user.id

    if user_id not in user_invoices:
        await callback.answer(
            "Дані інвойсу більше недоступні.",
            show_alert=True
        )
        return

    await callback.answer()

    await callback.message.answer(
        "✏️ Оберіть поле, яке потрібно виправити:",
        reply_markup=edit_fields_keyboard()
    )


# ============================================================
# Користувач обрав поле
# ============================================================

@router.callback_query(
    F.data.startswith("edit_field:")
)
async def edit_field_handler(
    callback: CallbackQuery
):
    user_id = callback.from_user.id

    if user_id not in user_invoices:
        await callback.answer(
            "Дані інвойсу більше недоступні.",
            show_alert=True
        )
        return

    field_key = callback.data.split(
        ":",
        1
    )[1]

    if field_key not in FIELD_NAMES:
        await callback.answer(
            "Невідоме поле.",
            show_alert=True
        )
        return

    user_invoices[user_id]["editing_field"] = field_key

    field_name = FIELD_NAMES[field_key]

    current_value = user_invoices[user_id][
        "data"
    ].get(
        field_key,
        ""
    )

    await callback.answer()

    await callback.message.answer(
        f"✏️ Поле: {field_name}\n\n"
        f"Поточне значення:\n"
        f"{current_value}\n\n"
        "Введіть правильне значення:"
    )


# ============================================================
# Кнопка "ℹ️ Допомога"
# ============================================================

@router.message(F.text == "ℹ️ Допомога")
async def help_button_handler(message: Message):
    await message.answer(
        "Я вмію працювати з інвойсами.\n\n"
        "Надішли інвойс як PDF, "
        "і я спробую отримати з нього інформацію.\n"
        "Але це не точно)"
    )


# Користувач вводить нове значення
# ============================================================

@router.message(F.text)
async def edit_value_handler(
    message: Message
):
    user_id = message.from_user.id

    if user_id not in user_invoices:
        return

    editing_field = user_invoices[user_id].get(
        "editing_field"
    )

    if not editing_field:
        return

    new_value = message.text.strip()

    if not new_value:
        await message.answer(
            "❌ Значення не може бути порожнім.\n"
            "Введіть правильне значення ще раз."
        )
        return

    # --------------------------------------------------------
    # Зберігаємо виправлене користувачем значення
    # --------------------------------------------------------

    user_invoices[user_id]["data"][
        editing_field
    ] = new_value

    user_invoices[user_id][
        "editing_field"
    ] = None

    logger.info(
        "User %s corrected invoice field %s.",
        user_id,
        editing_field,
    )

    # --------------------------------------------------------
    # Показуємо оновлений інвойс
    # --------------------------------------------------------

    await message.answer(
        "✅ Значення оновлено.\n\n"
        + build_invoice_text(
            user_invoices[user_id]["data"]
        ),
        reply_markup=confirmation_keyboard()
    )


# ============================================================