import json

from openai_client import ask_gpt_with_invoice


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
джерела для перевірки та пошуку інформації.

Не вигадуй значення.

Поверни ТІЛЬКИ валідний JSON за цією схемою:

{
  "document_type": "",
  "document_number": "",
  "date": "",
  "supplier": "",
  "recipient": "",
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

ВАЖЛИВА ЛОГІКА УЧАСНИКІВ:

1. "supplier" — компанія або особа, яка надає
   товар або послугу.

   Наприклад:
   Mokonzi Group Kft

2. "recipient" — Customer / клієнт / покупець,
   тобто особа або компанія, яка отримує товар
   або послугу.

   Наприклад:
   Mustafa Zerkol

3. "payment_provider" — платіжна система,
   платіжний посередник або інша компанія,
   через яку здійснюється оплата.

   Наприклад:
   SYMOCO PAYMENTS LTD

4. payment_provider НЕ є supplier тільки тому,
   що його назва знаходиться поруч із банківськими
   реквізитами.

5. payment_provider НЕ є recipient.

6. Якщо supplier і payment_provider — різні компанії,
   це нормально і НЕ є помилкою.

7. Якщо в інвойсі прямо або за контекстом видно,
   що банківські реквізити належать платіжній системі
   або платіжному посереднику, не замінюй ними supplier.

8. Якщо payment_provider неможливо достовірно визначити,
   залиш це поле порожнім.

9. Не вигадуй payment_provider тільки через назву
   банку або IBAN.

10. Банк — це фінансова установа, а не payment_provider,
    якщо в документі немає підстав вважати інакше.

БАНКІВСЬКІ РЕКВІЗИТИ:

- "iban" — IBAN, вказаний у документі.
- "swift" — SWIFT/BIC, вказаний у документі.
- "bank" — назва банку.
- "bank_address" — адреса банку.

Не вважай назву банку payment_provider.

Не вважай payment_provider банком.

Якщо payment_provider вказаний у документі,
збережи його окремо.

ЗАГАЛЬНІ ПРАВИЛА:

- Оригінальний PDF має найвищий пріоритет.
- Якщо parser відрізняється від PDF — використовуй PDF.
- Якщо дані з pypdf відрізняються від PDF —
  використовуй PDF.
- Не вигадуй значення.
- Якщо поле відсутнє — залиш його порожнім.
- Не додавай нових полів.
- Не використовуй Markdown.
- Поверни тільки валідний JSON.
- VAT повертай у форматі "0.00%".
- Якщо recipient має адресу, включи повну адресу.
- Якщо supplier має адресу і вона є частиною
  відповідного поля, включи її.
- Не змінюй назви компаній.
- Не скорочуй назви компаній.
- Перевіряй номер документа безпосередньо за PDF.
- Перевіряй дату безпосередньо за PDF.
- Перевіряй IBAN та SWIFT особливо уважно.
- Не змінюй символи IBAN та SWIFT.

ОСОБЛИВО:

Якщо в документі є структура на кшталт:

Supplier:
Mokonzi Group Kft

Customer:
Mustafa Zerkol

Payment / Beneficiary / Payment Provider:
SYMOCO PAYMENTS LTD

це потрібно трактувати як три різні ролі:

supplier = Mokonzi Group Kft
recipient = Mustafa Zerkol
payment_provider = SYMOCO PAYMENTS LTD

Не об'єднуй ці ролі.
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

    return json.loads(response)