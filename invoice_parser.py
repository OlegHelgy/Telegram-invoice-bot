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
        "Постачальник": "",
        "Отримувач": "",
        "Платіжна система": "",
        "Опис": "",
        "Кількість": "",
        "Ціна": "",
        "ПДВ": "",
        "Разом": "",
        "Валюта": "",
        "IBAN": "",
        "SWIFT": "",
        "Банк": "",
        "Адреса банку": "",
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
        r"(?:Invoice Number|Invoice No\.?|Number|No\.?)\s*[:#]?\s*([A-Za-z0-9-]+)",
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
    # Постачальник
    # ==========================================

    match = re.search(
        r"Account Owner\s+(.+)",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Постачальник"] = match.group(1).strip()

    # ==========================================
    # Отримувач / Customer
    # ==========================================

    match = re.search(
        r"Customer\s*:?\s*(.+)",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Отримувач"] = match.group(1).strip()

    # Старий варіант
    if not result["Отримувач"]:
        match = re.search(
            r"Your reference \(please mention on the transfer\)\s+(.+)",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Отримувач"] = match.group(1).strip()

    # ==========================================
    # Платіжна система / Payment Provider
    # ==========================================
    #
    # Важливо:
    # це НЕ supplier і НЕ customer.
    #
    # Шукаємо тільки явно позначену роль.
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
            result["Платіжна система"] = match.group(1).strip()
            break

    # Якщо в документі використовується Beneficiary,
    # не записуємо його автоматично в платіжну систему.
    #
    # Це навмисно:
    # GPT повинен визначити роль за контекстом PDF.

    # ==========================================
    # Опис
    # ==========================================

    match = re.search(
        r"CDE-\d+\s+(.+?)\s+1\.00\s+Quantity",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Опис"] = match.group(1).strip()

    if not result["Опис"]:
        match = re.search(
            r"Description\s*:?\s*(.+)",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Опис"] = match.group(1).strip()

    # ==========================================
    # Кількість
    # ==========================================

    match = re.search(
        r"CDE-\d+\s+.+?\s+([\d.]+)\s+Quantity",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Кількість"] = match.group(1)

    if not result["Кількість"]:
        match = re.search(
            r"Qty\.?\s*:?\s*([\d.,]+)",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Кількість"] = match.group(1)

    # ==========================================
    # Ціна
    # ==========================================

    match = re.search(
        r"CDE-\d+\s+.+?\s+[\d.]+\s+Quantity\s+([\d'.,]+)",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Ціна"] = match.group(1)

    if not result["Ціна"]:
        match = re.search(
            r"Unit price\s*:?\s*([\d'.,]+)",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Ціна"] = match.group(1)

    # ==========================================
    # ПДВ
    # ==========================================

    match = re.search(
        r"CDE-\d+\s+.+?\s+[\d.]+\s+Quantity\s+[\d'.,]+\s+([\d.]+)",
        text,
        re.IGNORECASE,
    )

    if match:
        result["ПДВ"] = match.group(1)

    if not result["ПДВ"]:
        match = re.search(
            r"VAT\s*:?\s*([\d.,]+)",
            text,
            re.IGNORECASE,
        )

        if match:
            result["ПДВ"] = match.group(1)

    # ==========================================
    # Разом
    # ==========================================

    match = re.search(
        r"Total\s+([A-Z]{3})\s+([\d'.,]+)",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Разом"] = match.group(2)
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
    # Адреса банку
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

    result["Адреса банку"] = ", ".join(address_parts)

    return result
