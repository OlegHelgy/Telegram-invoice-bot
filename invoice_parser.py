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
        "Платежная система": "",
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

    # ==========================================
    # Тип документа
    # ==========================================

    if re.search(r"Invoice pro forma", text, re.IGNORECASE):
        result["Тип документа"] = "Invoice pro forma"

    elif re.search(r"PRO FORMA INVOICE", text, re.IGNORECASE):
        result["Тип документа"] = "PRO FORMA INVOICE"

    # ==========================================
    # Номер документа
    # ==========================================

    match = re.search(
        r"(?:Invoice Number|Invoice No\.?|Number|No\.?)\s*[:#]?\s*([A-Z0-9-]+)",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Номер документа"] = match.group(1).strip()

    # CDE-009639
    if not result["Номер документа"]:
        match = re.search(r"\b(CDE-\d+)\b", text)

        if match:
            result["Номер документа"] = match.group(1)

    # D-MKNZ-588
    if not result["Номер документа"]:
        match = re.search(
            r"\b(D-[A-Z0-9]+-\d+)\b",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Номер документа"] = match.group(1)

    # ==========================================
    # Дата
    # ==========================================

    match = re.search(
        r"Date\s+(\d{2}[./-]\d{2}[./-]\d{4})",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Дата"] = match.group(1)

    # ==========================================
    # Валюта
    # ==========================================

    match = re.search(
        r"Currency\s+([A-Z]{3})",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Валюта"] = match.group(1).upper()

    # ==========================================
    # Поставщик
    # ==========================================

    match = re.search(
        r"Account Owner\s+(.+)",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Поставщик"] = match.group(1).strip()

    # ==========================================
    # Получатель / Customer
    # ==========================================

    match = re.search(
        r"Customer\s*:?\s*(.+)",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Получатель"] = match.group(1).strip()

    # Старый вариант
    if not result["Получатель"]:
        match = re.search(
            r"Your reference \(please mention on the transfer\)\s+(.+)",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Получатель"] = match.group(1).strip()

    # ==========================================
    # Платежная система / Payment Provider
    # ==========================================
    #
    # Важно:
    # это НЕ supplier и НЕ customer.
    #
    # Ищем только явно обозначенную роль.
    #

    payment_provider_patterns = [
        r"Payment Provider\s*:?\s*(.+)",
        r"Payment Processor\s*:?\s*(.+)",
        r"Payment System\s*:?\s*(.+)",
        r"Payment Service Provider\s*:?\s*(.+)",
    ]

    for pattern in payment_provider_patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            result["Платежная система"] = match.group(1).strip()
            break

    # Если в документе используется Beneficiary,
    # не записываем его автоматически в платежную систему.
    #
    # Это намеренно:
    # GPT должен определить роль по контексту PDF.

    # ==========================================
    # Описание
    # ==========================================

    match = re.search(
        r"CDE-\d+\s+(.+?)\s+1\.00\s+Quantity",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Описание"] = match.group(1).strip()

    if not result["Описание"]:
        match = re.search(
            r"Description\s*:?\s*(.+)",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Описание"] = match.group(1).strip()

    # ==========================================
    # Количество
    # ==========================================

    match = re.search(
        r"CDE-\d+\s+.+?\s+([\d.]+)\s+Quantity",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Количество"] = match.group(1)

    if not result["Количество"]:
        match = re.search(
            r"Qty\.?\s*:?\s*([\d.,]+)",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Количество"] = match.group(1)

    # ==========================================
    # Цена
    # ==========================================

    match = re.search(
        r"CDE-\d+\s+.+?\s+[\d.]+\s+Quantity\s+([\d'.,]+)",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Цена"] = match.group(1)

    if not result["Цена"]:
        match = re.search(
            r"Unit price\s*:?\s*([\d'.,]+)",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Цена"] = match.group(1)

    # ==========================================
    # НДС
    # ==========================================

    match = re.search(
        r"CDE-\d+\s+.+?\s+[\d.]+\s+Quantity\s+[\d'.,]+\s+([\d.]+)",
        text,
        re.IGNORECASE,
    )

    if match:
        result["НДС"] = match.group(1)

    if not result["НДС"]:
        match = re.search(
            r"VAT\s*:?\s*([\d.,]+)",
            text,
            re.IGNORECASE,
        )

        if match:
            result["НДС"] = match.group(1)

    # ==========================================
    # Итого
    # ==========================================

    match = re.search(
        r"Total\s+([A-Z]{3})\s+([\d'.,]+)",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Итого"] = match.group(2)
        result["Валюта"] = match.group(1).upper()

    # ==========================================
    # IBAN
    # ==========================================

    match = re.search(
        r"IBAN(?: Number)?\s*:?\s*([A-Z]{2}[A-Z0-9 ]{10,})",
        text,
        re.IGNORECASE,
    )

    if match:
        result["IBAN"] = match.group(1).strip()

    # ==========================================
    # SWIFT / BIC
    # ==========================================

    match = re.search(
        r"(?:SWIFT|Swift Code|BIC)\s*:?\s*([A-Z0-9]{8,11})",
        text,
        re.IGNORECASE,
    )

    if match:
        result["SWIFT"] = match.group(1).strip()

    # ==========================================
    # Банк
    # ==========================================

    match = re.search(
        r"Bank\s*:?\s*(.+)",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Банк"] = match.group(1).strip()

    # ==========================================
    # Адрес банка
    # ==========================================

    place_match = re.search(
        r"Place\s+(.+)",
        text,
        re.IGNORECASE,
    )

    postal_match = re.search(
        r"(\d{4,5})\s*-\s*(.+)",
        text,
        re.IGNORECASE,
    )

    address_parts = []

    if place_match:
        address_parts.append(
            place_match.group(1).strip()
        )

    if postal_match:
        address_parts.append(
            f"{postal_match.group(1)} - {postal_match.group(2).strip()}"
        )

    result["Адрес банка"] = ", ".join(address_parts)

    return result