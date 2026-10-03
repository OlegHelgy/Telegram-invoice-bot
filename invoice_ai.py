import json
import re

from openai_client import ask_gpt_with_invoice


def _strip_code_fences(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*\n?",
            "",
            text,
        )

        text = re.sub(
            r"\n?```\s*$",
            "",
            text,
        )

    return text.strip()


def _normalize_result(result: dict) -> dict:
    """
    Нормализация результата GPT.

    Важно:
    - total должен содержать только сумму;
    - currency должна содержать только валюту;
    - iban может содержать Account number,
      если настоящий IBAN отсутствует;
    - не добавляем значения, которых GPT не вернул.
    """

    if not isinstance(result, dict):
        raise ValueError(
            "GPT повернув не JSON-об'єкт."
        )

    # ---------------------------------------------------------
    # TOTAL
    # ---------------------------------------------------------

    total = result.get("total", "")

    if total is None:
        total = ""

    total = str(total).strip()

    # Если GPT случайно вернул:
    # "50,160.00 USD"
    # разделяем сумму и валюту.
    if total:
        match = re.match(
            r"^\s*([0-9][0-9\s,.\']*)\s*([A-Za-z]{3})\s*$",
            total,
        )

        if match:
            amount = match.group(1).strip()
            detected_currency = match.group(2).upper()

            result["total"] = amount

            # Не перезаписываем currency,
            # если она уже корректно указана.
            if not result.get("currency"):
                result["currency"] = detected_currency

    # ---------------------------------------------------------
    # CURRENCY
    # ---------------------------------------------------------

    currency = result.get("currency", "")

    if currency is None:
        currency = ""

    currency = str(currency).strip()

    # Убираем случайные пробелы/форматирование.
    currency_match = re.search(
        r"\b(USD|EUR|GBP|AED|SGD|HKD|CHF|CAD|AUD|JPY|CNY|PLN|CZK|HUF|RON|SEK|NOK|DKK|TRY)\b",
        currency.upper(),
    )

    if currency_match:
        result["currency"] = currency_match.group(1)
    else:
        result["currency"] = currency.upper()

    # ---------------------------------------------------------
    # IBAN / ACCOUNT NUMBER
    # ---------------------------------------------------------

    iban = result.get("iban", "")

    if iban is None:
        iban = ""

    iban = str(iban).strip()

    # Если GPT вернул текст вроде:
    # "Account number: 47410656108 USD"
    # оставляем только номер.
    account_match = re.search(
        r"(?:Account\s*number\s*[:\-]?\s*)?([A-Z]{2}[0-9A-Z]{10,34}|[0-9]{6,20})",
        iban,
        re.IGNORECASE,
    )

    if account_match:
        result["iban"] = account_match.group(1).upper()
    else:
        result["iban"] = iban

    # ---------------------------------------------------------
    # SWIFT
    # ---------------------------------------------------------

    swift = result.get("swift", "")

    if swift is None:
        swift = ""

    result["swift"] = str(swift).strip().upper()

    # ---------------------------------------------------------
    # VAT
    # ---------------------------------------------------------

    vat = result.get("vat", "")

    if vat is None:
        vat = ""

    vat = str(vat).strip()

    if vat:
        vat_match = re.search(
            r"([0-9]+(?:\.[0-9]+)?)\s*%",
            vat,
        )

        if vat_match:
            try:
                result["vat"] = (
                    f"{float(vat_match.group(1)):.2f}%"
                )
            except ValueError:
                result["vat"] = vat
        else:
            result["vat"] = vat

    return result


def build_invoice_prompt(
    extracted_text: str,
    parser_result: dict,
) -> str:

    return """
Ти аналізуєш інвойс.

У тебе є три джерела інформації:

1. Оригінальний PDF-документ.
2. Текст, який локально витягнув pypdf.
3. Результат локального parser.

Твоє завдання — визначити найбільш точні дані
безпосередньо з оригінального PDF.

Оригінальний PDF є головним джерелом істини.

pypdf та локальний parser використовуй як допоміжні
джерела для пошуку інформації.

Не довіряй parser автоматично.

Якщо parser показує очевидно неправильне значення,
а в PDF є правильне — використовуй PDF.

Не вигадуй значення.


ПОВЕРНИ ТІЛЬКИ ВАЛІДНИЙ JSON:

{
  "document_type": "",
  "document_number": "",
  "date": "",

  "supplier": "",
  "supplier_address": "",

  "recipient": "",
  "recipient_address": "",

  "payment_provider": "",

  "description": "",
  "quantity": "",
  "unit_price": "",
  "vat": "",
  "total": "",
  "currency": "",

  "iban": "",
  "swift": "",
  "bank": "",
  "bank_address": ""
}


============================================================
РОЛІ
============================================================

supplier — компанія або особа, яка надає товар
або послугу.

recipient — Customer / клієнт / покупець,
тобто тот, кто платит за товар або послугу.

payment_provider — платіжна система або платіжний
посередник, якщо він явно вказаний у документі.

payment_provider НЕ є supplier.

payment_provider НЕ є recipient.

Назва банку НЕ є payment_provider.


============================================================
АДРЕСИ
============================================================

Назву компанії або ім'я зберігай окремо від адреси.

supplier:
Mokonzi Group Kft

supplier_address:
2766 Tápiószele, Szelényi út 11. B. ép., HUNGARY

НЕ об'єднуй їх в одне поле.

Так само для recipient.


============================================================
СУМА
============================================================

"total" повинен містити ТІЛЬКИ числову суму.

Правильно:

"total": "50160.00"

Неправильно:

"total": "50,160.00 USD"

Валюта повинна бути окремо:

"currency": "USD"


============================================================
ВАЛЮТА
============================================================

"currency" повинна містити тільки код валюти.

Наприклад:

USD
EUR
GBP
AED
SGD
HKD

Не додавай валюту до поля total.


ВАЖЛИВО:

Визначай валюту безпосередньо за оригінальним PDF.

Не використовуй значення parser, якщо parser
витягнув очевидний текстовий шум.

Наприклад:

Parser:
Валюта: NET

але PDF показує:

USD

результат повинен бути:

"currency": "USD"


============================================================
IBAN / ACCOUNT NUMBER
============================================================

Якщо в документі є справжній IBAN —
використовуй саме його.

Якщо справжнього IBAN немає, але є
Account number — поле "iban" у нашій системі
може містити цей Account number.


ВАЖЛИВО:

Account number — це НЕ обов'язково IBAN.

Але якщо справжнього IBAN немає,
ми використовуємо Account number у полі "iban",
щоб зберегти платіжний рахунок.


============================================================
ВИБІР ACCOUNT NUMBER ЗА ВАЛЮТОЮ
============================================================

Якщо в документі є:

Account number: 47410656501 EUR
Account number: 47410656108 USD

і invoice currency = USD,

результат:

"iban": "47410656108"
"currency": "USD"


Якщо invoice currency = EUR:

"iban": "47410656501"
"currency": "EUR"


НЕ використовуй EUR Account number для USD invoice.

НЕ використовуй USD Account number для EUR invoice.


АЛГОРИТМ:

1. Спочатку визнач валюту інвойсу.
2. Знайди всі Account number.
3. Визнач валюту кожного рахунку.
4. Вибери рахунок, валюта якого збігається
   з валютою інвойсу.
5. Якщо є справжній IBAN — він має пріоритет.
6. Якщо Account number неможливо однозначно
   пов'язати з валютою інвойсу — залиш поле
   "iban" порожнім.
7. Ніколи не вигадуй рахунок.


============================================================
ПЛАТІЖНІ РЕКВІЗИТИ
============================================================

Для визначення рахунку, на який потрібно
здійснити оплату, пріоритет мають блоки:

Payment Details
Bank Details
Payment Instructions
Beneficiary
Beneficiary Details
Banking Details

Якщо в цих блоках вказано Account number,
використовуй його.

Не використовуй Account number постачальника
або клієнта, якщо документ явно показує інший
рахунок у Payment / Bank Details.


============================================================
SWIFT / BIC
============================================================

"swift" повинен містити SWIFT/BIC саме банку,
на рахунок якого здійснюється оплата.

Якщо SWIFT явно вказаний у платіжних реквізитах,
збережи його без змін.

Не замінюй SWIFT банку SWIFT платіжного
посередника.


============================================================
БАНК
============================================================

"bank" повинен містити назву банку,
який обслуговує рахунок для оплати.

Наприклад:

"bank":
"Standard Chartered Bank (Hong Kong) Limited"

Не використовуй назву payment_provider
як bank.

Якщо назва банку явно вказана біля SWIFT
або Payment Details — використовуй її.


============================================================
АДРЕСА БАНКУ
============================================================

"bank_address" повинна містити тільки адресу
банку, якщо вона явно вказана.

НЕ використовуй:

- supplier_address
- recipient_address
- payment_provider address

як bank_address.

Якщо адреса банку не вказана —
залиш:

"bank_address": ""


============================================================
ВАЖЛИВА ПЕРЕВІРКА ПЛАТІЖНИХ РЕКВІЗИТІВ
============================================================

Особливо уважно перевір:

1. валюту інвойсу;
2. Account number;
3. IBAN;
4. SWIFT/BIC;
5. банк;
6. адресу банку.

Наприклад, якщо PDF містить:

Account number: 47410656108 USD
SWIFT: SCBLHKHH
Bank: Standard Chartered Bank (Hong Kong) Limited

і invoice total:

50,160.00 USD

результат повинен бути:

"total": "50160.00",
"currency": "USD",
"iban": "47410656108",
"swift": "SCBLHKHH",
"bank": "Standard Chartered Bank (Hong Kong) Limited"


============================================================
НЕ ИСПОЛЬЗУЙ ШУМ PARSER
============================================================

Якщо parser показує:

"Разом": "1"

але в PDF видно:

"50,160.00 USD"

використовуй:

"total": "50160.00"
"currency": "USD"

Parser може витягнути випадковий номер,
наприклад номер сторінки, номер таблиці,
текст NET або інший PDF-шум.

Не використовуй такі значення,
якщо вони суперечать PDF.


============================================================
ЗАГАЛЬНІ ПРАВИЛА
============================================================

- Оригінальний PDF має найвищий пріоритет.
- Parser є допоміжним джерелом.
- pypdf є допоміжним джерелом.
- Не вигадуй значення.
- Якщо поле відсутнє — залиш його порожнім.
- Не додавай нових полів.
- Не використовуй Markdown.
- Поверни тільки JSON.
- VAT повертай у форматі "0.00%".
- Не змінюй назви компаній.
- Не скорочуй назви компаній.
- Не змінюй IBAN.
- Не змінюй Account number.
- Не змінюй SWIFT/BIC.
- Перевіряй номер документа безпосередньо за PDF.
- Перевіряй дату безпосередньо за PDF.
- Перевіряй total безпосередньо за PDF.
- Перевіряй currency безпосередньо за PDF.
- Перевіряй Account number відповідно до валюти.
- Перевіряй SWIFT/BIC.
- Перевіряй банк.
- Не використовуй адресу відправника як адресу банку.


============================================================
КРИТИЧНО ВАЖЛИВО
============================================================

Якщо PDF містить кілька банківських рахунків
у різних валютах, не вибирай перший рахунок.

Вибирай рахунок, валюта якого відповідає
валюті invoice.

Якщо invoice:

50,160.00 USD

і:

Account number: 47410656501 EUR
Account number: 47410656108 USD

результат:

"iban": "47410656108"
"currency": "USD"


Якщо invoice:

16,675.90 EUR

і:

Account number: 47410656501 EUR
Account number: 47410656108 USD

результат:

"iban": "47410656501"
"currency": "EUR"


Не вибирай рахунок тільки тому,
що він перший у документі.


============================================================
ПРИКЛАД РОЛЕЙ
============================================================

Supplier:
Mokonzi Group Kft
2766 Tápiószele, Szelényi út 11. B. ép., HUNGARY

Customer:
Mustafa Zerkol
Germany, DE-59067 Hamm, Konrad-Biermann-Weg 23

Payment Provider:
SYMOCO PAYMENTS LTD

Це означає:

supplier = Mokonzi Group Kft

supplier_address =
2766 Tápiószele, Szelényi út 11. B. ép., HUNGARY

recipient = Mustafa Zerkol

recipient_address =
Germany, DE-59067 Hamm, Konrad-Biermann-Weg 23

payment_provider = SYMOCO PAYMENTS LTD


Не об'єднуй ролі.

Не об'єднуй ім'я та адресу.

Не використовуй адресу supplier
як bank_address.


ПОВЕРНИ ТІЛЬКИ JSON.
"""


def analyze_invoice(
    pdf_path: str,
    extracted_text: str,
    parser_result: dict,
) -> dict:

    prompt = build_invoice_prompt(
        extracted_text,
        parser_result,
    )

    response = ask_gpt_with_invoice(
        pdf_path=pdf_path,
        extracted_text=extracted_text,
        parser_result=parser_result,
        prompt=prompt,
    )

    cleaned = _strip_code_fences(response)

    try:
        result = json.loads(cleaned)

    except json.JSONDecodeError as e:
        print(
            "Не вдалося розпарсити відповідь GPT як JSON:"
        )

        print(repr(response))

        raise ValueError(
            "GPT повернув відповідь у некоректному форматі."
        ) from e

    result = _normalize_result(result)

    return result