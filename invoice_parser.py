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


def _clean_spaces(value: str) -> str:
    """
    Прибирає зайві пробіли та переноси рядків.
    """

    value = str(value or "").strip()

    if not value:
        return ""

    return " ".join(value.split())


def _extract_block(
    text: str,
    start_pattern: str,
    end_patterns: list[str],
) -> str:
    """
    Витягує текстовий блок між двома маркерами.

    Використовується для Customer / Supplier та подібних
    багаторядкових блоків.
    """

    match = re.search(
        start_pattern,
        text,
        re.IGNORECASE,
    )

    if not match:
        return ""

    value = text[match.end():]

    for end_pattern in end_patterns:
        end_match = re.search(
            end_pattern,
            value,
            re.IGNORECASE,
        )

        if end_match:
            value = value[:end_match.start()]

    return _clean_spaces(value)


def parse_invoice(file_path: str) -> dict:
    text = extract_pdf_text(file_path)

    result = {
        "Тип документа": "",
        "Номер документа": "",
        "Дата": "",
        "Отримувач": "",
        "Платник": "",
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

    # ==================================================
    # Тип документа
    # ==================================================

    if re.search(
        r"Invoice pro forma",
        text,
        re.IGNORECASE,
    ):
        result["Тип документа"] = "Invoice pro forma"

    elif re.search(
        r"PRO FORMA INVOICE",
        text,
        re.IGNORECASE,
    ):
        result["Тип документа"] = "PRO FORMA INVOICE"

    # ==================================================
    # Номер документа
    # Ищем все кандидаты после Invoice Number / Invoice No.
    # и отбрасываем служебные слова вроде DATE.
    number_matches = re.findall(
        r"Invoice\s+(?:Number|No\.?)\s*[:#]?\s*([A-Za-z0-9-]+)",
        text,
        re.IGNORECASE,
    )

    invalid_document_numbers = {
        "DATE",
        "NUMBER",
        "NO",
        "INVOICE",
    }

    for candidate in number_matches:
        candidate = candidate.strip()
        if candidate.upper() not in invalid_document_numbers:
            result["Номер документа"] = candidate
            break

    # Отдельный случай PDF:
    # "INVOICE INVOICE NO. DATE ... SM16 ..."
    if not result["Номер документа"]:
        number_matches = re.findall(
            r"\bINVOICE\s+NO\.?\s*([A-Za-z0-9-]+)",
            text,
            re.IGNORECASE,
        )

        for candidate in number_matches:
            candidate = candidate.strip()
            if candidate.upper() not in invalid_document_numbers:
                result["Номер документа"] = candidate
                break

    # Для данного формата Silly Media номер имеет вид SM16.
    # Используем это только как fallback, если явный номер не найден.
    if not result["Номер документа"]:
        match = re.search(
            r"\bSM\d+\b",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Номер документа"] = match.group(0).upper()

    # CDE-009639
    if not result["Номер документа"]:
        match = re.search(
            r"\b(CDE-\d+)\b",
            text,
            re.IGNORECASE,
        )

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

    # ==================================================
    # Дата
    # ==================================================

    match = re.search(
        r"Date\s+(\d{2}[./-]\d{2}[./-]\d{4})",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Дата"] = match.group(1)

    # ==================================================
    # Валюта
    # ==================================================

    match = re.search(
        r"Currency\s+([A-Z]{3})",
        text,
        re.IGNORECASE,
    )

    if match:
        currency_value = match.group(1).upper()
        # NET / GROSS та подібні слова не є валютами.
        if currency_value not in {"NET", "GROSS", "TOTAL", "AMOUNT"}:
            result["Валюта"] = currency_value

    # ==================================================
    # ОТРИМУВАЧ
    #
    # У цьому інвойсі:
    #
    # Mokonzi Group Kft
    # 2766 Tápiószele, Szelényi út 11. B. ép., HUNGARY
    #
    # є отримувачем послуги / замовником.
    #
    # Адреса повинна зберігатися разом з назвою.
    # ==================================================

    customer_match = re.search(
        r"Customer\s*:?\s*(.+?)(?=\n\s*(?:Payment|Completion|Issue|Due|Description|Qty|Quantity|Total|$))",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if customer_match:
        customer_block = _clean_spaces(
            customer_match.group(1)
        )

        if customer_block:
            result["Отримувач"] = customer_block

    # Якщо Customer не знайшовся, пробуємо знайти
    # блок за типовою структурою PDF.

    if not result["Отримувач"]:

        match = re.search(
            r"Customer\s*:?\s*(.+)",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Отримувач"] = _clean_spaces(
                match.group(1)
            )

    # ==================================================
    # ПЛАТНИК
    #
    # Платник — окрема роль.
    #
    # Наприклад:
    #
    # Mustafa Zerkol
    # Germany, DE-59067 Hamm, Konrad-Biermann-Weg 23
    #
    # Не змішуємо його з отримувачем.
    # ==================================================

    payer_patterns = [
        r"Payer\s*:?\s*(.+?)(?=\n\s*(?:Payment|Completion|Issue|Due|Description|Qty|Quantity|Total|$))",
        r"Bill To\s*:?\s*(.+?)(?=\n\s*(?:Payment|Completion|Issue|Due|Description|Qty|Quantity|Total|$))",
        r"Customer\s+Name\s*:?\s*(.+?)(?=\n\s*(?:Payment|Completion|Issue|Due|Description|Qty|Quantity|Total|$))",
    ]

    for pattern in payer_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE | re.DOTALL,
        )

        if match:
            payer_block = _clean_spaces(
                match.group(1)
            )

            if payer_block:
                result["Платник"] = payer_block

            break

    # ==================================================
    # Старий варіант:
    #
    # Your reference...
    #
    # Використовуємо лише якщо Платник ще не знайдений.
    # ==================================================

    if not result["Платник"]:

        match = re.search(
            r"Your reference \(please mention on the transfer\)\s+(.+)",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Платник"] = _clean_spaces(
                match.group(1)
            )

    # ==================================================
    # СПЕЦІАЛЬНА ЛОГІКА ДЛЯ ВАШОГО ІНВОЙСУ
    #
    # У ньому Customer фактично є отримувачем послуги,
    # а платник вказаний окремо в PDF.
    #
    # Якщо в тексті є структура:
    #
    # Customer:
    # Mustafa Zerkol
    # Germany...
    #
    # Account Owner:
    # Mokonzi Group Kft
    # 2766 Tápiószele...
    #
    # тоді Account Owner стає Отримувачем,
    # а Customer — Платником.
    # ==================================================

    account_owner_match = re.search(
        r"Account Owner\s*:?\s*(.+?)(?=\n\s*(?:Bank|Customer|Payment|Completion|Issue|Due|Description|Total|$))",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if account_owner_match:

        account_owner_block = _clean_spaces(
            account_owner_match.group(1)
        )

        if account_owner_block:

            # Account Owner у цьому типі інвойсу —
            # постачальник послуги / отримувач платежу.
            #
            # У фінальній картці ми називаємо його
            # "Отримувач".

            result["Отримувач"] = account_owner_block

    # ==================================================
    # Якщо Customer знайдений,
    # і Account Owner став Отримувачем,
    # Customer стає Платником.
    # ==================================================

    customer_for_payer = re.search(
        r"Customer\s*:?\s*(.+?)(?=\n\s*(?:Payment|Completion|Issue|Due|Description|Qty|Quantity|Total|$))",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if (
        customer_for_payer
        and account_owner_match
    ):

        customer_block = _clean_spaces(
            customer_for_payer.group(1)
        )

        if customer_block:
            result["Платник"] = customer_block

    # ==================================================
    # ПЛАТІЖНА СИСТЕМА
    # ==================================================

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

            result["Платіжна система"] = _clean_spaces(
                match.group(1)
            )

            break

    # ==================================================
    # ДОДАТКОВИЙ ПОШУК SYMOCO
    #
    # Не прив'язуємо назву до Bank.
    # Це окрема платіжна система.
    # ==================================================

    if not result["Платіжна система"]:

        match = re.search(
            r"\b(SYMOCO\s+PAYMENTS\s+LTD)\b",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Платіжна система"] = _clean_spaces(
                match.group(1)
            )

    # ==================================================
    # Опис
    # ==================================================

    match = re.search(
        r"CDE-\d+\s+(.+?)\s+1\.00\s+Quantity",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Опис"] = _clean_spaces(
            match.group(1)
        )

    if not result["Опис"]:

        match = re.search(
            r"Description\s*:?\s*(.+)",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Опис"] = _clean_spaces(
                match.group(1)
            )

    # ==================================================
    # Кількість
    # ==================================================

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

    # ==================================================
    # Ціна
    # ==================================================

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

    # ==================================================
    # ПДВ
    # ==================================================

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

    # ==================================================
    # Разом
    # ==================================================

    # Основний формат: Total USD 50,160.00
    match = re.search(
        r"\bTotal\s+([A-Z]{3})\s+([\d\'.,]+)",
        text,
        re.IGNORECASE,
    )

    if match:
        result["Разом"] = match.group(2)
        result["Валюта"] = match.group(1).upper()

    # Деякі PDF мають формат: NET 50,160.00 USD.
    # NET не є валютою. Дозволяємо перенос рядка між частинами.
    if (
        not result["Разом"]
        or not result["Валюта"]
        or result["Валюта"].upper() in {"NET", "GROSS", "TOTAL", "AMOUNT"}
    ):
        match = re.search(
            r"\bNET\s+([\d\'.,]+)\s+([A-Z]{3})\b",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Разом"] = match.group(1)
            result["Валюта"] = match.group(2).upper()

    # Додатковий формат: Total / Net Amount / Amount 50,160.00 USD.
    if not result["Разом"] or not result["Валюта"]:
        match = re.search(
            r"\b(?:Total|Net\s+Amount|Amount)\s*[:#-]?\s*([\d\'.,]+)\s+([A-Z]{3})\b",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Разом"] = match.group(1)
            result["Валюта"] = match.group(2).upper()

    # Якщо сума вже знайдена, але валюта ще порожня,
    # шукаємо валюту безпосередньо після цієї суми.
    if result["Разом"] and not result["Валюта"]:
        normalized_total = re.escape(result["Разом"].strip())
        match = re.search(
            rf"{normalized_total}\s*([A-Z]{{3}})\b",
            text,
            re.IGNORECASE,
        )

        if match:
            result["Валюта"] = match.group(1).upper()

    # ==================================================
    # IBAN / ACCOUNT NUMBER
    #
    # 1. Якщо в документі є справжній IBAN —
    #    використовуємо його.
    #
    # 2. Якщо справжнього IBAN немає, шукаємо
    #    Account number з валютою.
    #
    # 3. Якщо є декілька рахунків:
    #    беремо Account number тієї валюти,
    #    яка вказана в інвойсі.
    #
    # Наприклад:
    #
    # Account number: 47410656501 EUR
    # Account number: 47410656108 USD
    #
    # Валюта інвойсу: USD
    #
    # Результат:
    # IBAN = 47410656108
    # ==================================================

    # --------------------------------------------------
    # 1. Спочатку справжній IBAN
    # --------------------------------------------------

    iban_match = re.search(
        r"\bIBAN(?:\s+Number)?\s*:?\s*"
        r"([A-Z]{2}[A-Z0-9 ]{10,})",
        text,
        re.IGNORECASE,
    )

    if iban_match:
        result["IBAN"] = _clean_spaces(
            iban_match.group(1)
        )

    # --------------------------------------------------
    # 2. Якщо IBAN немає — шукаємо Account number
    # --------------------------------------------------

    if not result["IBAN"]:

        account_matches = re.findall(
            r"\bAccount\s+number\s*:?\s*"
            r"([A-Z0-9][A-Z0-9 .'-]*?)"
            r"\s+([A-Z]{3})\b",
            text,
            re.IGNORECASE,
        )

        # Нормалізуємо валюту інвойсу
        invoice_currency = (
                result.get("Валюта", "")
                or ""
        ).strip().upper()

        # --------------------------------------------------
        # 3. Вибираємо Account number тієї ж валюти
        # --------------------------------------------------

        selected_account = ""

        for account_number, account_currency in account_matches:

            account_number = _clean_spaces(
                account_number
            )

            account_currency = (
                    account_currency
                    or ""
            ).strip().upper()

            if (
                    invoice_currency
                    and account_currency == invoice_currency
            ):
                selected_account = account_number
                break

        # --------------------------------------------------
        # 4. Якщо валюта не визначилась або збігу немає,
        #    НЕ вгадуємо рахунок.
        # --------------------------------------------------

        if selected_account:
            result["IBAN"] = selected_account

    # ==================================================
    # SWIFT / BIC
    #
    # У деяких інвойсах блок BILL TO містить SWIFT платника,
    # а реквізити отримувача платежу знаходяться вище і мають
    # окремий BIC.
    #
    # Спочатку шукаємо BIC/SWIFT саме у верхньому блоці
    # перед BILL TO, щоб не взяти SWIFT платника.
    # ==================================================

    supplier_payment_block = text

    bill_to_match = re.search(
        r"\bBILL\s+TO\b",
        text,
        re.IGNORECASE,
    )

    if bill_to_match:
        supplier_payment_block = text[:bill_to_match.start()]

    # Найнадійніший варіант: BIC у блоці реквізитів
    # отримувача платежу.
    match = re.search(
        r"\bBIC\s*:?\s*([A-Z0-9]{8,11})\b",
        supplier_payment_block,
        re.IGNORECASE,
    )

    if match:
        result["SWIFT"] = match.group(1).strip().upper()
    else:
        # Для інших форматів PDF у верхньому блоці
        # допускаємо SWIFT / Swift Code.
        match = re.search(
            r"(?:SWIFT|Swift Code)\s*:?\s*([A-Z0-9]{8,11})\b",
            supplier_payment_block,
            re.IGNORECASE,
        )

        if match:
            result["SWIFT"] = match.group(1).strip().upper()
        else:
            # Останній fallback для форматів, де немає BILL TO.
            match = re.search(
                r"\bBIC\s*:?\s*([A-Z0-9]{8,11})\b",
                text,
                re.IGNORECASE,
            )

            if match:
                result["SWIFT"] = match.group(1).strip().upper()
            else:
                match = re.search(
                    r"(?:SWIFT|Swift Code)\s*:?\s*([A-Z0-9]{8,11})\b",
                    text,
                    re.IGNORECASE,
                )

                if match:
                    result["SWIFT"] = match.group(1).strip().upper()

    # Банк отримувача платежу
    # ==================================================
    # ВАЖЛИВО:
    # Блок BILL TO належить платнику. Якщо в ньому є
    # "Bank name", не можна використовувати це значення
    # як банк отримувача.
    #
    # Тому назву банку шукаємо тільки у верхньому блоці
    # реквізитів отримувача, тобто до BILL TO.

    recipient_payment_block = text

    bill_to_match = re.search(
        r"\bBILL\s+TO\b",
        text,
        re.IGNORECASE,
    )

    if bill_to_match:
        recipient_payment_block = text[:bill_to_match.start()]

    bank_match = re.search(
        r"(?:Bank\s+name|Bank\s+Name|Bank)\s*:?\s*(.+)",
        recipient_payment_block,
        re.IGNORECASE,
    )

    if bank_match:

        bank_value = _clean_spaces(
            bank_match.group(1)
        )

        # "Bank Details" — заголовок блоку, а не назва банку.
        if bank_value.strip().lower() not in {
            "details",
            "detail",
            "information",
            "info",
        }:
            bank_value = re.split(
                r"\b(?:BIC|SWIFT|IBAN|Bank\s+address|Address)\b",
                bank_value,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip(" ,;:")

            if bank_value and bank_value.lower() not in {
                "details",
                "detail",
                "information",
                "info",
            }:
                result["Банк"] = bank_value

    # Якщо назва банку не витягнулась через поле Bank,
    # шукаємо відому повну назву безпосередньо у платіжному блоці.
    if not result["Банк"]:
        bank_name_patterns = [
            r"\b(Standard\s+Chartered\s+Bank\s*\(Hong\s+Kong\)\s+Limited)\b",
            r"\b(WIO\s+BANK\s+P\.J\.S\.C\.)\b",
        ]

        for pattern in bank_name_patterns:
            match = re.search(
                pattern,
                recipient_payment_block,
                re.IGNORECASE,
            )

            if match:
                result["Банк"] = _clean_spaces(match.group(1))
                break

    # Якщо назва банку не вказана явно, але відомий BIC,
    # використовуємо тільки однозначне співвідношення BIC -> банк.
    swift_to_bank = {
        "WIOBAEADXXX": "WIO BANK P.J.S.C.",
        "WIOBAEAD": "WIO BANK P.J.S.C.",
        "SCBLHKHH": "Standard Chartered Bank (Hong Kong) Limited",
    }

    if not result["Банк"] and result["SWIFT"]:
        result["Банк"] = swift_to_bank.get(
            result["SWIFT"].upper(),
            "",
        )

    # ==================================================
    # Адреса банку
    # ==================================================
    # Не беремо адресу з BILL TO: це може бути адреса
    # банку платника. Якщо адреса банку отримувача не
    # вказана в інвойсі, залишаємо поле порожнім.

    bank_address_match = re.search(
        r"Bank\s+address\s*:?\s*(.+)",
        recipient_payment_block,
        re.IGNORECASE,
    )

    if bank_address_match:
        result["Адреса банку"] = _clean_spaces(
            bank_address_match.group(1)
        )
    else:
        result["Адреса банку"] = ""

    return result