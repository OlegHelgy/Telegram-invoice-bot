from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from invoice_parser import parse_invoice
from keyboards.main_menu import main_menu


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Привіт! Я бот для читання інвойсів.\n"
        "Обери дію:",
        reply_markup=main_menu,
    )


@router.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "Привіт! Я бот для читання інвойсів.\n"
        "Обери дію:",
        reply_markup=main_menu,
    )


@router.message(F.text == "📄 Інвойс")
async def invoice_button_handler(message: Message):
    await message.answer(
        "Надішли мені інвойс у вигляді зображення або документа."
    )


@router.message(F.text == "ℹ️ Допомога")
async def help_button_handler(message: Message):
    await message.answer(
        "Я вмію працювати з інвойсами.\n\n"
        "Надішли інвойс як зображення або документ, "
        "і я спробую отримати з нього інформацію."
    )


@router.message(F.photo)
async def invoice_photo_handler(message: Message):
    print("PHOTO HANDLER WORKS")

    try:
        photo = message.photo[-1]

        await message.bot.download(
            photo,
            destination="downloads/invoice.jpg"
        )

        print("Invoice saved to downloads/invoice.jpg")

        result = parse_invoice("downloads/invoice.jpg")

        print("Parser result:")
        print(result)

        await message.answer(
            "Інвойс отримано та оброблено.\n\n"
            f"{result}"
        )

    except Exception as error:
        print(f"Invoice image processing error: {error}")

        await message.answer(
            "Не вдалося обробити зображення інвойсу.\n"
            "Спробуй надіслати його ще раз."
        )


@router.message(F.document)
async def invoice_document_handler(message: Message):
    print("DOCUMENT HANDLER WORKS")

    document = message.document

    try:
        await message.bot.download(
            document,
            destination="downloads/invoice.pdf"
        )

        print("Invoice PDF saved to downloads/invoice.pdf")

        result = parse_invoice("downloads/invoice.pdf")

        print("Parser result:")
        print(result)

        await message.answer(
            "Інвойс отримано та оброблено.\n\n"
            f"Тип документа: {result['Тип документа']}\n"
            f"Номер: {result['Номер документа']}\n"
            f"Дата: {result['Дата']}\n"
            f"Постачальник: {result['Поставщик']}\n"
            f"Отримувач: {result['Получатель']}\n"
            f"Опис: {result['Описание']}\n"
            f"Кількість: {result['Количество']}\n"
            f"Ціна: {result['Цена']}\n"
            f"ПДВ: {result['НДС']}\n"
            f"Сума: {result['Итого']} {result['Валюта']}\n"
            f"IBAN: {result['IBAN']}\n"
            f"SWIFT: {result['SWIFT']}\n"
            f"Банк: {result['Банк']}\n"
            f"Адреса банку: {result['Адрес банка']}"
        )

    except Exception as error:
        print(f"Invoice processing error: {error}")

        await message.answer(
            "Не вдалося обробити інвойс.\n"
            "Спробуй надіслати PDF ще раз."
        )