import asyncio
import os
import re
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from invoice_parser import extract_pdf_text, parse_invoice
from invoice_ai import analyze_invoice
from invoice_reconciliation import reconcile_invoice

from keyboards.main_menu import main_menu


router = Router()


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
    "supplier": "Постачальник",
    "recipient": "Отримувач",
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
# Текст фінальної інформації
# ============================================================

def build_invoice_text(data: dict) -> str:
    return (
        "📄 Інформація з інвойсу\n\n"

        f"Тип документа: {data.get('document_type', '')}\n"
        f"Номер: {data.get('document_number', '')}\n"
        f"Дата: {data.get('date', '')}\n\n"

        f"Постачальник: {data.get('supplier', '')}\n"
        f"Отримувач: {data.get('recipient', '')}\n\n"

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
# Клавіатура вибору поля
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
# Клавіатура після конфлікту
# ============================================================

def conflict_keyboard():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="✏️ Виправити",
        callback_data="invoice_edit"
    )

    builder.adjust(1)

    return builder.as_markup()


# ============================================================
# Допомога
# ============================================================

HELP_TEXT = (
    "ℹ️ Допомога\n\n"

    "Я аналізую PDF-інвойси та витягую з них основну інформацію:\n"
    "• номер документа\n"
    "• дату\n"
    "• постачальника\n"
    "• отримувача\n"
    "• опис послуги\n"
    "• кількість\n"
    "• ціну\n"
    "• ПДВ\n"
    "• суму\n"
    "• валюту\n"
    "• IBAN\n"
    "• SWIFT\n"
    "• банк\n"
    "• адресу банку\n\n"

    "Якщо parser і GPT знаходять різні значення, "
    "бот покаже розбіжність.\n\n"

    "Щоб виправити інформацію:\n"
    "1. Натисніть «✏️ Є помилка».\n"
    "2. Виберіть потрібне поле.\n"
    "3. Введіть правильне значення звичайним повідомленням.\n\n"

    "Наприклад, для адреси банку:\n"
    "Konstitucijos pr. 7, 09308 Vilnius, Lithuania\n\n"

    "⚠️ Перед використанням завжди перевіряйте "
    "дані з оригінальним інвойсом."
)


# ============================================================
# Захист від випадкового / сміттєвого тексту
# ============================================================

def looks_like_garbage(value: str) -> bool:
    value = value.strip()

    if not value:
        return True

    # Максимальна довжина
    if len(value) > 500:
        return True

    # Має бути хоча б одна літера
    if not re.search(
        r"[A-Za-zА-Яа-яІіЇїЄєҐґ]",
        value
    ):
        return True

    # Повторення одного символу
    #
    # aaaaaaaa
    # 11111111
    # ........
    if re.search(
        r"(.)\1{6,}",
        value,
        re.IGNORECASE
    ):
        return True

    letters_only = re.sub(
        r"[^A-Za-zА-Яа-яІіЇїЄєҐґ]",
        "",
        value
    ).lower()

    if len(letters_only) >= 15:

        unique_ratio = (
            len(set(letters_only))
            / len(letters_only)
        )

        if unique_ratio < 0.30:
            return True

    return False


# ============================================================
# Нормалізація тексту
# ============================================================

def normalize_text(value: str) -> str:
    value = value.strip()

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value


# ============================================================
# Нормалізація дати
# ============================================================

def normalize_date(value: str):
    value = value.strip()

    normalized = re.sub(
        r"[-/]",
        ".",
        value
    )

    match = re.fullmatch(
        r"(\d{1,2})\.(\d{1,2})\.(\d{4})",
        normalized
    )

    if not match:
        return None

    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3))

    if year < 1900 or year > 2100:
        return None

    try:
        date_obj = datetime(
            year,
            month,
            day
        )

    except ValueError:
        return None

    return date_obj.strftime(
        "%d.%m.%Y"
    )


# ============================================================
# Нормалізація адреси банку
# ============================================================

def normalize_bank_address(value: str) -> str:

    value = value.strip()

    # Bank Address:
    value = re.sub(
        r"^\s*bank\s+address\s*:?\s*",
        "",
        value,
        flags=re.IGNORECASE
    )

    # Адреса банку:
    value = re.sub(
        r"^\s*адреса\s+банку\s*:?\s*",
        "",
        value,
        flags=re.IGNORECASE
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# Перевірка адреси банку
# ============================================================

def validate_bank_address(value: str):

    value = value.strip()

    if not value:
        return (
            False,
            "Адреса не може бути порожньою."
        )

    if len(value) < 8:
        return (
            False,
            "Адреса занадто коротка."
        )

    if len(value) > 250:
        return (
            False,
            "Адреса занадто довга."
        )

    # Адреса повинна містити цифру:
    # номер будинку,
    # поштовий індекс,
    # офіс тощо.
    if not re.search(
        r"\d",
        value
    ):
        return (
            False,
            "В адресі не знайдено номера "
            "будинку або поштового індексу."
        )

    letters = re.findall(
        r"[A-Za-zА-Яа-яІіЇїЄєҐґ]",
        value
    )

    if len(letters) < 4:
        return (
            False,
            "Адреса повинна містити "
            "текстову частину."
        )

    words = re.findall(
        r"[A-Za-zА-Яа-яІіЇїЄєҐґ]+",
        value
    )

    for word in words:

        if len(word) >= 15:

            unique_ratio = (
                len(set(word.lower()))
                / len(word)
            )

            if unique_ratio < 0.45:
                return (
                    False,
                    "Схоже на випадковий "
                    "набір символів."
                )

    compact = re.sub(
        r"\s+",
        "",
        value
    ).lower()

    if len(compact) >= 15:

        unique_ratio = (
            len(set(compact))
            / len(compact)
        )

        if unique_ratio < 0.25:
            return (
                False,
                "Схоже на випадковий "
                "набір символів."
            )

    return True, ""


# ============================================================
# Перевірка та нормалізація поля
# ============================================================

def validate_and_normalize_field(
    field: str,
    value: str
):
    """
    Повертає:

        (True, normalized_value, "")

    або:

        (False, None, error_message)
    """

    value = value.strip()

    # --------------------------------------------------------
    # Порожнє значення
    # --------------------------------------------------------

    if not value:

        return (
            False,
            None,
            "❌ Значення не може бути порожнім.\n"
            "Введіть правильне значення ще раз."
        )

    # --------------------------------------------------------
    # Дата
    # --------------------------------------------------------

    if field == "date":

        normalized_date = normalize_date(
            value
        )

        if normalized_date is None:

            return (
                False,
                None,
                "❌ Некоректна дата.\n\n"
                "Введіть дату у форматі:\n"
                "ДД.ММ.РРРР\n\n"
                "Наприклад:\n"
                "24.09.2026"
            )

        return (
            True,
            normalized_date,
            ""
        )

    # --------------------------------------------------------
    # Адреса банку
    # --------------------------------------------------------

    if field == "bank_address":

        normalized_address = (
            normalize_bank_address(
                value
            )
        )

        is_valid, error = (
            validate_bank_address(
                normalized_address
            )
        )

        if not is_valid:

            return (
                False,
                None,
                "❌ Некоректне значення.\n\n"
                "Будь ласка, введіть справжню "
                "адресу банку одним повідомленням.\n\n"
                "Наприклад:\n"
                "Konstitucijos pr. 7, "
                "09308 Vilnius, Lithuania"
            )

        return (
            True,
            normalized_address,
            ""
        )

    # --------------------------------------------------------
    # Отримувач
    # --------------------------------------------------------

    if field == "recipient":

        normalized = normalize_text(
            value
        )

        if len(normalized) < 2:

            return (
                False,
                None,
                "❌ Некоректний отримувач.\n"
                "Введіть ім'я або повну назву."
            )

        if len(normalized) > 250:

            return (
                False,
                None,
                "❌ Значення занадто довге."
            )

        if looks_like_garbage(
            normalized
        ):

            return (
                False,
                None,
                "❌ Схоже, введене значення "
                "некоректне.\n\n"
                "Будь ласка, введіть правильного "
                "отримувача ще раз."
            )

        return (
            True,
            normalized,
            ""
        )

    # --------------------------------------------------------
    # Постачальник
    # --------------------------------------------------------

    if field == "supplier":

        normalized = normalize_text(
            value
        )

        if len(normalized) < 2:

            return (
                False,
                None,
                "❌ Некоректний постачальник.\n"
                "Введіть назву компанії."
            )

        if len(normalized) > 250:

            return (
                False,
                None,
                "❌ Значення занадто довге."
            )

        if looks_like_garbage(
            normalized
        ):

            return (
                False,
                None,
                "❌ Схоже, введене значення "
                "некоректне."
            )

        return (
            True,
            normalized,
            ""
        )

    # --------------------------------------------------------
    # Опис
    # --------------------------------------------------------

    if field == "description":

        normalized = normalize_text(
            value
        )

        if len(normalized) < 2:

            return (
                False,
                None,
                "❌ Опис занадто короткий."
            )

        if len(normalized) > 500:

            return (
                False,
                None,
                "❌ Опис занадто довгий."
            )

        return (
            True,
            normalized,
            ""
        )

    # --------------------------------------------------------
    # Кількість
    # --------------------------------------------------------

    if field == "quantity":

        normalized = (
            value
            .replace(",", ".")
            .replace(" ", "")
            .replace("'", "")
        )

        try:
            number = float(
                normalized
            )

        except ValueError:

            return (
                False,
                None,
                "❌ Некоректна кількість.\n"
                "Введіть число, наприклад: 1.00"
            )

        if number < 0:

            return (
                False,
                None,
                "❌ Кількість не може бути "
                "від'ємною."
            )

        return (
            True,
            normalized,
            ""
        )

    # --------------------------------------------------------
    # Ціна
    # --------------------------------------------------------

    if field == "unit_price":

        normalized = (
            value
            .replace("'", "")
            .replace(" ", "")
            .replace(",", ".")
        )

        try:
            number = float(
                normalized
            )

        except ValueError:

            return (
                False,
                None,
                "❌ Некоректна ціна.\n"
                "Введіть число, наприклад: 6000.00"
            )

        if number < 0:

            return (
                False,
                None,
                "❌ Ціна не може бути "
                "від'ємною."
            )

        return (
            True,
            normalized,
            ""
        )

    # --------------------------------------------------------
    # ПДВ
    # --------------------------------------------------------

    if field == "vat":

        normalized = (
            value
            .replace("%", "")
            .replace(",", ".")
            .strip()
        )

        try:
            vat_number = float(
                normalized
            )

        except ValueError:

            return (
                False,
                None,
                "❌ Некоректний ПДВ.\n"
                "Введіть, наприклад: 0.00"
            )

        if vat_number < 0 or vat_number > 100:

            return (
                False,
                None,
                "❌ ПДВ повинен бути "
                "від 0 до 100%."
            )

        return (
            True,
            f"{vat_number:.2f}%",
            ""
        )

    # --------------------------------------------------------
    # Сума
    # --------------------------------------------------------

    if field == "total":

        normalized = (
            value
            .replace("'", "")
            .replace(" ", "")
            .replace(",", ".")
        )

        try:
            number = float(
                normalized
            )

        except ValueError:

            return (
                False,
                None,
                "❌ Некоректна сума.\n"
                "Введіть число, наприклад: 6000.00"
            )

        if number < 0:

            return (
                False,
                None,
                "❌ Сума не може бути "
                "від'ємною."
            )

        return (
            True,
            normalized,
            ""
        )

    # --------------------------------------------------------
    # Валюта
    # --------------------------------------------------------

    if field == "currency":

        normalized = value.upper().strip()

        if not re.fullmatch(
            r"[A-Z]{3}",
            normalized
        ):

            return (
                False,
                None,
                "❌ Некоректна валюта.\n"
                "Використовуйте 3-літерний код, "
                "наприклад: EUR, CHF, USD."
            )

        return (
            True,
            normalized,
            ""
        )

    # --------------------------------------------------------
    # IBAN
    # --------------------------------------------------------

    if field == "iban":

        normalized = re.sub(
            r"\s+",
            "",
            value
        ).upper()

        if not re.fullmatch(
            r"[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}",
            normalized
        ):

            return (
                False,
                None,
                "❌ Некоректний IBAN.\n"
                "Перевірте введене значення."
            )

        formatted = " ".join(
            normalized[i:i + 4]
            for i in range(
                0,
                len(normalized),
                4
            )
        )

        return (
            True,
            formatted,
            ""
        )

    # --------------------------------------------------------
    # SWIFT
    # --------------------------------------------------------

    if field == "swift":

        normalized = value.upper().strip()

        if not re.fullmatch(
            r"[A-Z0-9]{8}([A-Z0-9]{3})?",
            normalized
        ):

            return (
                False,
                None,
                "❌ Некоректний SWIFT/BIC.\n"
                "Повинен містити 8 або 11 символів."
            )

        return (
            True,
            normalized,
            ""
        )

    # --------------------------------------------------------
    # Тип документа / номер / банк
    # --------------------------------------------------------

    if field in {
        "document_type",
        "document_number",
        "bank",
    }:

        normalized = normalize_text(
            value
        )

        if len(normalized) < 2:

            return (
                False,
                None,
                "❌ Значення занадто коротке."
            )

        if len(normalized) > 250:

            return (
                False,
                None,
                "❌ Значення занадто довге."
            )

        if looks_like_garbage(
            normalized
        ):

            return (
                False,
                None,
                "❌ Схоже, введене значення "
                "некоректне.\n\n"
                "Будь ласка, введіть правильне "
                "значення ще раз."
            )

        return (
            True,
            normalized,
            ""
        )

    # --------------------------------------------------------
    # Інші поля
    # --------------------------------------------------------

    normalized = normalize_text(
        value
    )

    if looks_like_garbage(
        normalized
    ):

        return (
            False,
            None,
            "❌ Схоже, введене значення "
            "некоректне.\n\n"
            "Будь ласка, введіть правильне "
            "значення ще раз."
        )

    return (
        True,
        normalized,
        ""
    )


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
        HELP_TEXT
    )


# ============================================================
# Кнопка "ℹ️ Допомога"
#
# ВАЖЛИВО:
# ЦЕЙ HANDLER ПОВИНЕН БУТИ ДО ЗАГАЛЬНОГО F.TEXT
# ============================================================

@router.message(F.text == "ℹ️ Допомога")
async def help_button_handler(message: Message):

    await message.answer(
        HELP_TEXT
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
# Обробка PDF
# ============================================================

@router.message(F.document)
async def invoice_document_handler(message: Message):

    print("DOCUMENT HANDLER WORKS")

    document = message.document

    file_name = (
        document.file_name or ""
    )

    if not file_name.lower().endswith(
        ".pdf"
    ):

        await message.answer(
            "Будь ласка, надішли інвойс "
            "у форматі PDF."
        )

        return

    os.makedirs(
        "downloads",
        exist_ok=True
    )

    # Унікальне ім'я файлу для кожного користувача та документа,
    # щоб паралельні завантаження не перезаписували одне одного.
    user_id = message.from_user.id

    file_path = (
        f"downloads/invoice_{user_id}_"
        f"{document.file_unique_id}.pdf"
    )

    try:

        # ----------------------------------------------------
        # 1. Зберігаємо PDF
        # ----------------------------------------------------

        await message.bot.download(
            document,
            destination=file_path
        )

        print(
            f"PDF інвойсу збережено: {file_path}"
        )

        await message.answer(
            "Інвойс отримано.\n"
            "Починаю обробку..."
        )

        # ----------------------------------------------------
        # 2. pypdf
        # ----------------------------------------------------

        extracted_text = await asyncio.to_thread(
            extract_pdf_text,
            file_path,
        )

        print(
            "Текст з PDF витягнуто"
        )

        # ----------------------------------------------------
        # 3. Локальний parser
        # ----------------------------------------------------

        local_result = await asyncio.to_thread(
            parse_invoice,
            file_path,
        )

        print(
            "Результат локального parser:"
        )

        print(
            local_result
        )

        # ----------------------------------------------------
        # 4. GPT
        #
        # Виносимо синхронний виклик OpenAI в окремий потік,
        # щоб не блокувати event loop бота.
        # ----------------------------------------------------

        ai_result = await asyncio.to_thread(
            analyze_invoice,
            file_path,
            extracted_text,
            local_result,
        )

        print(
            "Результат GPT:"
        )

        print(
            ai_result
        )

        # ----------------------------------------------------
        # 5. Звірка результатів
        # ----------------------------------------------------

        reconciliation_result = (
            reconcile_invoice(
                local_result,
                ai_result
            )
        )

        print(
            "Результат звірки:"
        )

        print(
            reconciliation_result
        )

        final_data = (
            reconciliation_result["data"]
        )

        conflicts = (
            reconciliation_result["conflicts"]
        )

        # ----------------------------------------------------
        # Зберігаємо дані ДО показу конфлікту
        #
        # Це важливо:
        # користувач повинен мати можливість
        # натиснути "Є помилка" навіть після конфлікту.
        # ----------------------------------------------------

        user_invoices[user_id] = {
            "data": final_data,
            "editing_field": None,
            "conflicts": conflicts,
            "confirmed": False,
        }

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
                "в оригінальному документі.\n\n"
                "Після перевірки натисніть "
                "«✏️ Виправити»."
            )

            await message.answer(
                conflict_text,
                reply_markup=conflict_keyboard()
            )

            return

        # ----------------------------------------------------
        # Конфліктів немає
        # ----------------------------------------------------

        await message.answer(
            build_invoice_text(
                final_data
            ),
            reply_markup=confirmation_keyboard()
        )

    except Exception as e:

        print(
            "Помилка обробки інвойсу:"
        )

        print(
            repr(e)
        )

        await message.answer(
            "❌ Не вдалося обробити інвойс.\n\n"
            "Можливо, документ має погану якість "
            "або його неможливо коректно розпізнати."
        )

    finally:

        # Прибираємо тимчасовий PDF, щоб не засмічувати диск.
        if os.path.exists(file_path):

            try:
                os.remove(file_path)

            except OSError as cleanup_error:
                print(
                    "Не вдалося видалити тимчасовий файл:"
                )
                print(repr(cleanup_error))


# ============================================================
# Обробка фотографії
# ============================================================

@router.message(F.photo)
async def invoice_photo_handler(message: Message):

    await message.answer(
        "Наразі обробка зображень "
        "ще не підключена.\n\n"
        "Будь ласка, надішли PDF-файл інвойсу."
    )


# ============================================================
# Кнопка "✅ Все правильно"
# ============================================================

@router.callback_query(
    F.data == "invoice_confirm"
)
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

    user_invoices[user_id][
        "confirmed"
    ] = True

    user_invoices[user_id][
        "editing_field"
    ] = None

    await callback.answer()

    await callback.message.answer(
        "✅ Дані інвойсу підтверджено."
    )

    print(
        f"Invoice confirmed by user {user_id}"
    )


# ============================================================
# Кнопка "✏️ Є помилка"
# ============================================================

@router.callback_query(
    F.data == "invoice_edit"
)
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

    user_invoices[user_id][
        "editing_field"
    ] = None

    await callback.answer()

    await callback.message.answer(
        "✏️ Оберіть поле, яке потрібно "
        "виправити:",
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

    user_invoices[user_id][
        "editing_field"
    ] = field_key

    field_name = FIELD_NAMES[
        field_key
    ]

    current_value = (
        user_invoices[user_id]["data"]
        .get(
            field_key,
            ""
        )
    )

    await callback.answer()

    await callback.message.answer(
        f"✏️ Поле: {field_name}\n\n"
        f"Поточне значення:\n"
        f"{current_value}\n\n"
        "Введіть правильне значення "
        "одним повідомленням:"
    )


# ============================================================
# Користувач вводить нове значення
#
# ВАЖЛИВО:
# цей handler стоїть ПІСЛЯ кнопки Допомога.
# Тому "ℹ️ Допомога" більше не перехоплюється тут.
# ============================================================

@router.message(F.text)
async def edit_value_handler(
    message: Message
):

    user_id = message.from_user.id

    if user_id not in user_invoices:
        return

    editing_field = (
        user_invoices[user_id]
        .get("editing_field")
    )

    if not editing_field:
        return

    new_value = (
        message.text or ""
    ).strip()

    # --------------------------------------------------------
    # Захист від повторного натискання кнопок
    # --------------------------------------------------------

    if new_value in {
        "ℹ️ Допомога",
        "📄 Інвойс",
    }:

        return

    # --------------------------------------------------------
    # Перевірка значення
    # --------------------------------------------------------

    is_valid, normalized_value, error = (
        validate_and_normalize_field(
            editing_field,
            new_value
        )
    )

    if not is_valid:

        await message.answer(
            error
        )

        return

    # --------------------------------------------------------
    # Зберігаємо нове значення
    # --------------------------------------------------------

    user_invoices[user_id][
        "data"
    ][editing_field] = normalized_value

    user_invoices[user_id][
        "editing_field"
    ] = None

    # Якщо це поле було конфліктним,
    # прибираємо його з конфліктів.
    conflicts = user_invoices[user_id].get(
        "conflicts",
        {}
    )

    if editing_field in conflicts:

        del conflicts[
            editing_field
        ]

    user_invoices[user_id][
        "conflicts"
    ] = conflicts

    user_invoices[user_id][
        "confirmed"
    ] = False

    print(
        f"User {user_id} corrected "
        f"{editing_field}: "
        f"{normalized_value}"
    )

    # --------------------------------------------------------
    # Показуємо оновлену фінальну інформацію
    # --------------------------------------------------------

    await message.answer(
        "✅ Значення оновлено.\n\n"
        + build_invoice_text(
            user_invoices[user_id]["data"]
        ),
        reply_markup=confirmation_keyboard()
    )