from aiogram.utils.keyboard import InlineKeyboardBuilder


CB_QUIZ_TOPIC = "quiz_topic"
CB_QUIZ_NEXT = "quiz_next"
CB_QUIZ_CHANGE = "quiz_change"
CB_QUIZ_END = "quiz_end"

QUIZ_TOPICS = [
    "Банки та платежі",
    "IBAN і SWIFT",
    "Валюти",
    "Карткові платежі",
]


def quiz_topics_keyboard():
    builder = InlineKeyboardBuilder()

    for topic in QUIZ_TOPICS:
        builder.button(
            text=topic,
            callback_data=f"{CB_QUIZ_TOPIC}:{topic}",
        )

    builder.adjust(2)
    return builder.as_markup()


def quiz_result_keyboard():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="➡️ Наступне питання",
        callback_data=CB_QUIZ_NEXT,
    )
    builder.button(
        text="🔄 Змінити тему",
        callback_data=CB_QUIZ_CHANGE,
    )
    builder.button(
        text="Закінчити",
        callback_data=CB_QUIZ_END,
    )

    builder.adjust(1)
    return builder.as_markup()
