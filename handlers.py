import logging
import os
import random

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from invoice_parser import extract_pdf_text, parse_invoice
from invoice_ai import analyze_invoice
from invoice_reconciliation import reconcile_invoice
from openai_client import (
    ask_gpt,
    ask_gpt_for_random_fact,
)

from keyboards.main_menu import main_menu
from keyboards.random_fact import (
    CB_RANDOM_END,
    CB_RANDOM_MORE,
    random_fact_keyboard,
)
from keyboards.quiz import (
    CB_QUIZ_CHANGE,
    CB_QUIZ_END,
    CB_QUIZ_NEXT,
    CB_QUIZ_TOPIC,
    quiz_result_keyboard,
    quiz_topics_keyboard,
)


router = Router()
logger = logging.getLogger(__name__)


# ============================================================
# Тимчасове зберігання даних користувачів
# ============================================================

user_invoices = {}

# Історія діалогу з ChatGPT для звичайних текстових запитів.
gpt_conversations = {}
MAX_GPT_MESSAGES = 10

quiz_sessions = {}


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
# Теми для випадкового факту
# ============================================================

PAYMENT_TOPICS = [
    "історія платежів",
    "банківські перекази",
    "карткові платежі",
    "безконтактні платежі",
    "онлайн-платежі",
    "платіжні системи",
    "IBAN",
    "SWIFT",
    "валюти",
    "фінансові технології",
]


RANDOM_FACT_PROMPT = """
Ти — експерт з цікавих фактів про платежі, банки та фінансові технології.
Розкажи один маловідомий, але достовірний факт на тему «{topic}».

Вимоги до факту:
- дивовижний для пересічної людини;
- легко запамʼятовується;
- викладений у 2-3 простих реченнях;
- зрозумілий без спеціальних знань;
- стосується платежів, банків, грошей або платіжних технологій.

Не повторюй загальновідомі факти. Не вигадуй статистику,
історичні події, назви компаній або технологій.

Відповідай українською. Не додавай вступів на кшталт
«Ось цікавий факт:» — одразу сам факт.
"""


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
# Випадковий факт про платежі
# ============================================================

async def send_random_fact(message: Message):
    topic = random.choice(PAYMENT_TOPICS)

    prompt = RANDOM_FACT_PROMPT.format(
        topic=topic
    )

    try:
        fact = ask_gpt_for_random_fact(
            prompt=prompt,
            image_path="assets/random_invoice_fact.png",
        )

        await message.answer(
            fact,
            reply_markup=random_fact_keyboard(),
        )

    except Exception:
        logger.exception(
            "Random fact generation failed for user %s.",
            message.from_user.id,
        )

        await message.answer(
            "😔 Не вдалося звʼязатися з ChatGPT. "
            "Спробуй ще раз за хвилину.",
            reply_markup=random_fact_keyboard(),
        )


@router.message(Command("random"))
async def random_fact_handler(message: Message):
    logger.info(
        "User %s requested a random payment fact.",
        message.from_user.id,
    )

    await message.answer_photo(
        photo=FSInputFile(
            "assets/random_invoice_fact.png"
        )
    )

    await send_random_fact(message)


@router.message(F.text == "🎲 Випадковий факт")
async def random_fact_button_handler(message: Message):
    await random_fact_handler(message)


@router.callback_query(F.data == CB_RANDOM_MORE)
async def random_more_handler(callback: CallbackQuery):
    await callback.answer()

    await callback.message.edit_reply_markup(
        reply_markup=None,
    )

    await send_random_fact(callback.message)


@router.callback_query(F.data == CB_RANDOM_END)
async def random_end_handler(callback: CallbackQuery):
    await callback.answer()

    await callback.message.edit_reply_markup(
        reply_markup=None,
    )

    await callback.message.answer(
        "Гаразд."
    )


# ============================================================
# ChatGPT інтерфейс
# ============================================================

CB_GPT_END = "gpt_end"


def gpt_end_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Закінчити розмову",
        callback_data=CB_GPT_END,
    )
    return builder.as_markup()


async def send_gpt_answer(message: Message, user_text: str):
    user_id = message.from_user.id
    history = gpt_conversations.setdefault(user_id, [])

    if history:
        conversation = "\n\n".join(
            f"Користувач: {user_message}\n"
            f"ChatGPT: {assistant_message}"
            for user_message, assistant_message in history
        )

        prompt = (
            "Продовжуй розмову з користувачем, враховуючи попередній "
            "контекст.\n\n"
            f"Попередня розмова:\n{conversation}\n\n"
            f"Нове повідомлення користувача: {user_text}"
        )
    else:
        prompt = user_text

    try:
        answer = ask_gpt(prompt)

        history.append((user_text, answer))
        if len(history) > MAX_GPT_MESSAGES:
            del history[:-MAX_GPT_MESSAGES]

        await message.answer(
            answer,
            reply_markup=gpt_end_keyboard(),
        )

    except Exception:
        logger.exception(
            "GPT request failed for user %s.",
            user_id,
        )

        await message.answer(
            "😔 Не вдалося отримати відповідь від ChatGPT. "
            "Спробуй ще раз."
        )



@router.message(Command("gpt"))
async def gpt_handler(message: Message):
    logger.info(
        "User %s requested GPT.",
        message.from_user.id,
    )

    await message.answer_photo(
        photo=FSInputFile(
            "assets/img.png",
        ),
    )

    user_text = message.text.removeprefix("/gpt").strip()

    if not user_text:
        await message.answer(
            "Напиши запит після команди /gpt.\n\n"
            "Наприклад:\n"
            "/gpt Розкажи, що таке IBAN."
        )
        return

    await send_gpt_answer(message, user_text)


@router.callback_query(F.data == CB_GPT_END)
async def gpt_end_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    gpt_conversations.pop(user_id, None)

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Розмову завершено. Можеш написати нове питання.")


@router.message(F.text == "🤖 ChatGPT")
async def gpt_button_handler(message: Message):
    user_id = message.from_user.id
    gpt_conversations.pop(user_id, None)
    gpt_conversations[user_id] = []

    logger.info(
        "User %s started a new GPT conversation.",
        user_id,
    )

    await message.answer_photo(
        photo=FSInputFile("assets/img.png"),
    )

    await message.answer(
        "Напиши своє питання, і я передам його ChatGPT."
    )


# ============================================================
# Квіз
# ============================================================

QUIZ_GENERATE_PROMPT = """
Створи одне питання для вікторини на тему «{topic}».

Вимоги до питання:
- перевіряє лише ОДИН конкретний факт або поняття;
- має одну чітку правильну відповідь;
- не обʼєднує два або більше терміни в одному питанні;
- не допускає кількох різних, але однаково правильних трактувань;
- відповідь має бути короткою і зрозумілою;
- користувач відповідатиме своїми словами, без варіантів відповіді;
- не використовуй питання, де правильними можуть бути одночасно загальна
  категорія і конкретний спосіб/метод.

Перед формуванням питання перевір, що запропонована правильна відповідь
однозначно відповідає саме цьому питанню.

Поверни результат рівно у такому форматі:
QUESTION: <одне чітке питання>
ANSWER: <коротка правильна відповідь>

Відповідай українською.
"""


QUIZ_CHECK_PROMPT = """
Перевір відповідь користувача на питання вікторини.

Питання: {question}
Правильна відповідь: {correct_answer}
Відповідь користувача: {user_answer}

Оцінюй відповідь за змістом, а не за дослівним збігом.
Вважай відповідь правильною, якщо вона передає той самий зміст,
використовує коректний синонім, іншу граматичну форму або загальноприйняте
скорочення.

Не вважай відповідь правильною, якщо вона лише частково відповідає питанню,
є занадто загальною замість конкретної правильної відповіді або змінює
сутність поняття.

Якщо питання саме по собі неоднозначне або правильна відповідь допускає
кілька рівноцінних трактувань, не карай користувача за формулювання, яке
логічно відповідає питанню.

Перша строка відповіді ОБОВʼЯЗКОВО має бути рівно одним із двох значень:
CORRECT
або
INCORRECT

На наступних 1-2 рядках коротко поясни результат українською.
Якщо відповідь правильна, коротко поясни, чому.
Якщо неправильна, коротко назви правильну відповідь і поясни помилку.
"""


async def send_quiz_question(
    message: Message,
    user_id: int,
):
    session = quiz_sessions[user_id]
    topic = session["topic"]

    prompt = QUIZ_GENERATE_PROMPT.format(topic=topic)

    try:
        result = ask_gpt(prompt)
        lines = [line.strip() for line in result.splitlines() if line.strip()]

        question = next(
            line.removeprefix("QUESTION:").strip()
            for line in lines
            if line.startswith("QUESTION:")
        )
        correct_answer = next(
            line.removeprefix("ANSWER:").strip()
            for line in lines
            if line.startswith("ANSWER:")
        )

        session["question"] = question
        session["correct_answer"] = correct_answer
        session["question_number"] += 1

        await message.answer(
            f"🧠 Питання {session['question_number']}\n\n"
            f"{question}\n\n"
            "Напиши свою відповідь повідомленням."
        )

    except Exception:
        logger.exception(
            "Quiz question generation failed for user %s.",
            user_id,
        )
        await message.answer(
            "😔 Не вдалося підготувати питання. Спробуй ще раз."
        )


@router.message(Command("quiz"))
async def quiz_handler(message: Message):
    user_id = message.from_user.id
    quiz_sessions.pop(user_id, None)

    logger.info(
        "User %s started a quiz.",
        user_id,
    )

    await message.answer_photo(
        photo=FSInputFile("assets/random_invoice_fact.png"),
    )

    await message.answer(
        "🧠 Обери тему квізу:",
        reply_markup=quiz_topics_keyboard(),
    )


@router.message(F.text == "🧠 Квіз")
async def quiz_button_handler(message: Message):
    await quiz_handler(message)


@router.callback_query(F.data.startswith(f"{CB_QUIZ_TOPIC}:"))
async def quiz_topic_handler(callback: CallbackQuery):
    topic = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    quiz_sessions[user_id] = {
        "topic": topic,
        "score": 0,
        "question_number": 0,
        "question": "",
        "correct_answer": "",
    }

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"Тема: {topic}\n\nПочинаємо!"
    )
    await send_quiz_question(
        callback.message,
        user_id,
    )


@router.callback_query(F.data == CB_QUIZ_NEXT)
async def quiz_next_handler(callback: CallbackQuery):
    user_id = callback.from_user.id

    if user_id not in quiz_sessions:
        await callback.answer("Квіз завершено.", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await send_quiz_question(
        callback.message,
        user_id,
    )


@router.callback_query(F.data == CB_QUIZ_CHANGE)
async def quiz_change_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    quiz_sessions.pop(user_id, None)

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "🧠 Обери нову тему:",
        reply_markup=quiz_topics_keyboard(),
    )


@router.callback_query(F.data == CB_QUIZ_END)
async def quiz_end_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    session = quiz_sessions.pop(user_id, None)

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    if session:
        await callback.message.answer(
            f"Квіз завершено. Твій результат: "
            f"{session['score']} / {session['question_number']}.",
            reply_markup=main_menu,
        )
    else:
        await callback.message.answer(
            "Квіз завершено.",
            reply_markup=main_menu,
        )


# ============================================================
# /start
# ============================================================

@router.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    quiz_sessions.pop(user_id, None)
    gpt_conversations.pop(user_id, None)

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

    quiz_session = quiz_sessions.get(user_id)
    if quiz_session and quiz_session.get("question"):
        user_answer = message.text.strip()
        if not user_answer:
            return

        prompt = QUIZ_CHECK_PROMPT.format(
            question=quiz_session["question"],
            correct_answer=quiz_session["correct_answer"],
            user_answer=user_answer,
        )

        try:
            result = ask_gpt(prompt)
            is_correct = (
                result.strip().splitlines()[0].strip()
                == "CORRECT"
            )

            if is_correct:
                quiz_session["score"] += 1
                status = "✅ Правильно!"
            else:
                status = "❌ Неправильно."

            explanation = "\n".join(
                line.strip()
                for line in result.splitlines()[1:]
                if line.strip()
            )

            await message.answer(
                f"{status}\n\n"
                f"{explanation}\n\n"
                f"Рахунок: {quiz_session['score']} / "
                f"{quiz_session['question_number']}",
                reply_markup=quiz_result_keyboard(),
            )

            quiz_session["question"] = ""
            quiz_session["correct_answer"] = ""

        except Exception:
            logger.exception(
                "Quiz answer check failed for user %s.",
                user_id,
            )
            await message.answer(
                "😔 Не вдалося перевірити відповідь. "
                "Спробуй ще раз."
            )

        return

    if user_id not in user_invoices:
        if user_id not in gpt_conversations:
            await message.answer_photo(
                photo=FSInputFile(
                    "assets/img.png",
                ),
            )

        await send_gpt_answer(message, message.text.strip())

        return

    editing_field = user_invoices[user_id].get(
        "editing_field"
    )

    if not editing_field:
        if user_id not in gpt_conversations:
            await message.answer_photo(
                photo=FSInputFile(
                    "assets/img.png",
                ),
            )

        await send_gpt_answer(message, message.text.strip())

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
