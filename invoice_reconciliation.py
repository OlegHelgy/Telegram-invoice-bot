def normalize_value(field: str, value: str) -> str:
    value = str(value or "").strip()

    if not value:
        return ""

    # ПДВ приводимо до єдиного формату
    # 0.00 -> 0.00%
    if field == "vat":
        if value.endswith("%"):
            return value

        try:
            number = float(value.replace(",", "."))
            return f"{number:.2f}%"
        except ValueError:
            return value

    # Прибираємо зайві пробіли
    if field in {
        "recipient",
        "bank_address",
        "payment_provider",
    }:
        return " ".join(value.split())

    return value


def normalize_address_for_comparison(value: str) -> str:
    """
    Нормалізація адреси тільки для порівняння.

    Початкове значення при цьому не змінюється.
    """

    value = value.lower().strip()

    # Наприклад:
    #
    # Place Saint-François 16, 1002 - Lausanne
    #
    # та
    #
    # Saint-François 16, 1002 - Lausanne
    #
    # вважаємо однією адресою.

    value = value.replace("place ", "")

    # Прибираємо зайві пробіли
    value = " ".join(value.split())

    return value


def reconcile_invoice(
    local_result: dict,
    ai_result: dict
) -> dict:
    """
    Порівнює результати локального parser та GPT.

    Джерела:
    - local_result — дані, отримані локальним parser
    - ai_result — дані, отримані GPT

    Правила:

    1. Якщо обидва значення порожні —
       поле залишається порожнім.

    2. Якщо значення є тільки у GPT —
       використовуємо GPT.

    3. Якщо значення є тільки у parser —
       використовуємо parser.

    4. Якщо значення збігаються —
       використовуємо більш повне значення.

    5. Для recipient та bank_address допускається,
       що GPT додав додаткову адресну інформацію.

    6. Якщо значення дійсно відрізняються —
       створюємо конфлікт і поки не обираємо
       значення автоматично.

    7. payment_provider є окремою роллю.
       Він не є автоматично постачальником,
       отримувачем або банком.
    """

    field_mapping = {
        "document_type": "Тип документа",
        "document_number": "Номер документа",
        "date": "Дата",

        "supplier": "Постачальник",
        "recipient": "Отримувач",

        # Платіжна система / платіжний провайдер
        #
        # Наприклад:
        # SYMOCO PAYMENTS LTD
        #
        # Це окрема роль і вона не повинна
        # автоматично замінювати постачальника.
        "payment_provider": "Платіжна система",

        "description": "Опис",
        "quantity": "Кількість",
        "unit_price": "Ціна",
        "vat": "ПДВ",
        "total": "Разом",
        "currency": "Валюта",

        "iban": "IBAN",
        "swift": "SWIFT",
        "bank": "Банк",
        "bank_address": "Адреса банку",
    }

    final_result = {}
    conflicts = {}

    for ai_field, local_field in field_mapping.items():

        ai_value = str(
            ai_result.get(ai_field, "") or ""
        ).strip()

        local_value = str(
            local_result.get(local_field, "") or ""
        ).strip()

        normalized_ai = normalize_value(
            ai_field,
            ai_value
        )

        normalized_local = normalize_value(
            ai_field,
            local_value
        )

        # -------------------------------------------------
        # 1. Обидва значення відсутні
        # -------------------------------------------------

        if not normalized_ai and not normalized_local:
            final_result[ai_field] = ""
            continue

        # -------------------------------------------------
        # 2. Значення є тільки у GPT
        # -------------------------------------------------

        if normalized_ai and not normalized_local:
            final_result[ai_field] = ai_value
            continue

        # -------------------------------------------------
        # 3. Значення є тільки у parser
        # -------------------------------------------------

        if normalized_local and not normalized_ai:
            final_result[ai_field] = local_value
            continue

        # -------------------------------------------------
        # 4. Спеціальна обробка отримувача
        #    та адреси банку
        # -------------------------------------------------

        if ai_field in {
            "recipient",
            "bank_address",
        }:

            ai_normalized = normalize_address_for_comparison(
                ai_value
            )

            local_normalized = normalize_address_for_comparison(
                local_value
            )

            # Наприклад:
            #
            # Parser:
            # Gomiashvili Peppilotta
            #
            # GPT:
            # Gomiashvili Peppilotta,
            # 29 Griboedova street, GEORGIA
            #
            # GPT містить більш повну інформацію.

            if (
                ai_normalized.startswith(local_normalized)
                or local_normalized.startswith(ai_normalized)
            ):

                if len(ai_value) >= len(local_value):
                    final_result[ai_field] = ai_value
                else:
                    final_result[ai_field] = local_value

                continue

            # Наприклад:
            #
            # Parser:
            # Saint-François 16, 1002 - Lausanne
            #
            # GPT:
            # Place Saint-François 16, 1002 - Lausanne
            #
            # Після нормалізації адреси збігаються.

            if ai_normalized == local_normalized:

                if len(ai_value) >= len(local_value):
                    final_result[ai_field] = ai_value
                else:
                    final_result[ai_field] = local_value

                continue

        # -------------------------------------------------
        # 5. Звичайний збіг
        # -------------------------------------------------

        if normalized_ai == normalized_local:

            # Якщо GPT дав більш повний рядок,
            # зберігаємо його.

            if len(ai_value) >= len(local_value):
                final_result[ai_field] = ai_value
            else:
                final_result[ai_field] = local_value

            continue

        # -------------------------------------------------
        # 6. Реальний конфлікт
        # -------------------------------------------------

        conflicts[ai_field] = {
            "parser": local_value,
            "gpt": ai_value,
        }

        # Не обираємо значення автоматично.
        # Користувач зможе перевірити та виправити
        # значення через бота.

        final_result[ai_field] = ""

    return {
        "data": final_result,
        "conflicts": conflicts,
    }