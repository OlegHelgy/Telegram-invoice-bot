from openai_client import ask_gpt


def build_invoice_prompt(text: str) -> str:
    return f"""
Ти аналізуєш текст інвойсу.

Витягни з документа тільки інформацію, яка реально присутня в тексті.

Поверни результат у такому форматі:

Тип документа:
Номер документа:
Дата:
Постачальник:
Отримувач:
Опис:
Кількість:
Ціна:
ПДВ:
Сума:
Валюта:
IBAN:
SWIFT:
Банк:
Адреса банку:

Якщо якесь поле відсутнє в документі, залиш його порожнім.
Не вигадуй значення.

Текст документа:

{text}
"""


def analyze_invoice_text(text: str) -> str:
    prompt = build_invoice_prompt(text)
    return ask_gpt(prompt)