from aiogram.utils.keyboard import InlineKeyboardBuilder


CB_RANDOM_MORE = "random_more"
CB_RANDOM_END = "random_end"


def random_fact_keyboard():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Хочу ще факт",
        callback_data=CB_RANDOM_MORE,
    )
    builder.button(
        text="Закінчити",
        callback_data=CB_RANDOM_END,
    )

    builder.adjust(2)

    return builder.as_markup()
