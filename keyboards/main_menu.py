from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📄 Інвойс"),
            KeyboardButton(text="🎲 Випадковий факт"),
        ],
        [
            KeyboardButton(text="ℹ️ Допомога"),
        ],
    ],
    resize_keyboard=True,
)