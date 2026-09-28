from pypdf import PdfReader
import re


def extract_pdf_text(file_path: str) -> str:
    reader = PdfReader(file_path)

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text


def parse_invoice(file_path: str) -> dict:
    text = extract_pdf_text(file_path)

    result = {
        "Тип документа": "",
        "Номер документа": "",
        "Дата": "",
        "Поставщик": "",
        "Получатель": "",
        "Описание": "",
        "Количество": "",
        "Цена": "",
        "НДС": "",
        "Итого": "",
        "Валюта": "",
        "IBAN": "",
        "SWIFT": "",
        "Банк": "",
        "Адрес банка": "",
    }

    # Тип документа
    if "Invoice pro forma" in text:
        result["Тип документа"] = "Invoice pro forma"

    # Номер документа / Sales order
    match = re.search(r"(CDE-\d+)", text)
    if match:
        result["Номер документа"] = match.group(1)

    # Дата
    match = re.search(r"Date\s+(\d{2}\.\d{2}\.\d{4})", text)
    if match:
        result["Дата"] = match.group(1)

    # Валюта
    match = re.search(r"Currency\s+([A-Z]{3})", text)
    if match:
        result["Валюта"] = match.group(1)

    # Поставщик
    match = re.search(
        r"Account Owner\s+(.+)",
        text
    )
    if match:
        result["Поставщик"] = match.group(1).strip()

    # Получатель
    match = re.search(
        r"Your reference \(please mention on the transfer\)\s+(.+)",
        text
    )
    if match:
        result["Получатель"] = match.group(1).strip()

    # Описание
    match = re.search(
        r"CDE-\d+\s+(.+?)\s+1\.00\s+Quantity",
        text
    )
    if match:
        result["Описание"] = match.group(1).strip()

    # Количество
    match = re.search(
        r"CDE-\d+\s+.+?\s+([\d.]+)\s+Quantity",
        text
    )
    if match:
        result["Количество"] = match.group(1)

    # Цена
    match = re.search(
        r"CDE-\d+\s+.+?\s+[\d.]+\s+Quantity\s+([\d'.,]+)",
        text
    )
    if match:
        result["Цена"] = match.group(1)

    # НДС
    match = re.search(
        r"CDE-\d+\s+.+?\s+[\d.]+\s+Quantity\s+[\d'.,]+\s+([\d.]+)",
        text
    )
    if match:
        result["НДС"] = match.group(1)

    # Итого
    match = re.search(
        r"Total\s+([A-Z]{3})\s+([\d'.,]+)",
        text
    )
    if match:
        result["Итого"] = match.group(2)
        result["Валюта"] = match.group(1)

    # IBAN
    match = re.search(
        r"IBAN Number\s+(.+)",
        text
    )
    if match:
        result["IBAN"] = match.group(1).strip()

    # SWIFT
    match = re.search(
        r"Swift Code\s+(.+)",
        text
    )
    if match:
        result["SWIFT"] = match.group(1).strip()

    # Банк
    match = re.search(
        r"Bank\s+(.+)",
        text
    )
    if match:
        result["Банк"] = match.group(1).strip()

    # Адрес банка
    place_match = re.search(
        r"Place\s+(.+)",
        text
    )

    postal_match = re.search(
        r"(\d{4})\s*-\s*(.+)",
        text
    )

    address_parts = []

    if place_match:
        address_parts.append(place_match.group(1).strip())

    if postal_match:
        address_parts.append(
            f"{postal_match.group(1)} - {postal_match.group(2).strip()}"
        )

    result["Адрес банка"] = ", ".join(address_parts)

    return result