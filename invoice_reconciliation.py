
import re


def normalize_value(field: str, value: str) -> str:
    value = str(value or "").strip()

    if not value:
        return ""

    if field == "vat":
        if value.endswith("%"):
            return value

        try:
            number = float(value.replace(",", "."))
            return f"{number:.2f}%"
        except ValueError:
            return value

    if field in {
        "supplier",
        "supplier_address",
        "recipient",
        "recipient_address",
        "bank_address",
        "payment_provider",
    }:
        return " ".join(value.split())

    return value


def normalize_address_for_comparison(value: str) -> str:
    value = str(value or "").lower().strip()
    value = value.replace("place ", "")
    value = " ".join(value.split())
    value = re.sub(r"[^0-9a-zа-яґєіїüöäßéèêàáőűúíó ,.-]", "", value)
    return value.strip(" ,")


_TABLE_HEADER_WORDS = {
    "qty",
    "quantity",
    "unitprice",
    "netprice",
    "grossprice",
    "vatvalue",
    "vat",
    "amount",
    "total",
    "description",
}


def _has_table_header_junk(value: str) -> bool:
    lowered = re.sub(r"[^a-z]", "", value.lower())
    if not lowered:
        return False

    hits = sum(1 for word in _TABLE_HEADER_WORDS if word in lowered)
    return hits >= 2


_PSEUDO_CURRENCIES = {
    "NET", "GROSS", "TOTAL", "AMOUNT", "VAT", "VALUE",
    "PRICE", "UNITPRICE", "NETPRICE", "GROSSPRICE",
}


def _is_pseudo_currency(value: str) -> bool:
    return str(value or "").strip().upper() in _PSEUDO_CURRENCIES


def _to_number(value: str):
    if not value:
        return None
    cleaned = str(value).replace(" ", "").replace("'", "").replace(",", "")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _is_obvious_parser_total_junk(
    local_total: str,
    ai_total: str,
    ai_quantity: str,
    ai_unit_price: str,
) -> bool:
    parser_number = _to_number(local_total)
    ai_number = _to_number(ai_total)
    quantity = _to_number(ai_quantity)
    unit_price = _to_number(ai_unit_price)

    if None in (parser_number, ai_number, quantity, unit_price):
        return False

    if parser_number == ai_number:
        return False

    expected = quantity * unit_price

    if abs(expected - ai_number) > max(0.01, abs(ai_number) * 0.0001):
        return False

    return parser_number <= 1


def _looks_like_number(value: str) -> bool:
    normalized = (
        value.replace("'", "")
        .replace(" ", "")
        .replace(",", ".")
    )

    try:
        float(normalized)
        return True
    except ValueError:
        return False


def _has_letters(value: str, min_count: int = 2) -> bool:
    letters = re.findall(r"[A-Za-zА-Яа-яІіЇїЄєҐґÀ-ÿ]", value)
    return len(letters) >= min_count


def is_parser_value_sane(field: str, value: str) -> bool:
    value = (value or "").strip()

    if not value:
        return False

    if field in {"quantity", "unit_price", "total"}:
        return _looks_like_number(value)

    if field == "vat":
        cleaned = value.replace("%", "").replace(",", ".").strip()
        try:
            number = float(cleaned)
        except ValueError:
            return False
        return 0 <= number <= 100

    if field == "currency":
        return bool(re.fullmatch(r"[A-Z]{3}", value.upper()))

    if field == "iban":
        compact = re.sub(r"\s+", "", value).upper()
        return bool(re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}", compact))

    if field == "swift":
        compact = value.upper().strip()
        if compact.startswith(("BIC", "SWIFT")):
            return False
        return bool(re.fullmatch(r"[A-Z0-9]{8}([A-Z0-9]{3})?", compact))

    if field == "date":
        return bool(re.fullmatch(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", value))

    if field in {
        "document_type",
        "document_number",
        "supplier",
        "supplier_address",
        "recipient",
        "recipient_address",
        "payment_provider",
        "description",
        "bank",
        "bank_address",
    }:
        if len(value) < 3 or len(value) > 500:
            return False

        if _has_table_header_junk(value):
            return False

        if field == "document_number":
            if not re.search(r"[A-Za-z0-9]", value):
                return False
            digits = re.sub(r"\D", "", value)
            letters = re.sub(r"[^A-Za-z]", "", value)
            if len(letters) == 0 and len(digits) >= 8:
                return False
        elif not _has_letters(value, min_count=2):
            return False

        if field in {"supplier_address", "recipient_address", "bank_address"}:
            if not re.search(r"\d", value):
                return False
            if not _has_letters(value, min_count=4):
                return False

        if field == "bank" and re.search(r"/(swift|bic|iban)", value, re.IGNORECASE):
            return False

        return True

    return True


def _compact_alnum(value: str) -> str:
    return re.sub(r"[^0-9a-zа-яґєії]", "", value.lower())


def _values_equivalent(ai_value: str, local_value: str) -> bool:
    ai_compact = _compact_alnum(ai_value)
    local_compact = _compact_alnum(local_value)

    if not ai_compact or not local_compact:
        return False

    if ai_compact == local_compact:
        return True

    if len(ai_compact) < 5 or len(local_compact) < 5:
        return False

    return ai_compact in local_compact or local_compact in ai_compact


def _extract_address_after_name(full_value: str, name: str) -> str:
    """Витягує адресу з рядка parser, якщо він злип ім'я та адресу."""
    full = " ".join(str(full_value or "").split())
    person = " ".join(str(name or "").split())

    if not full or not person:
        return ""

    compact_full = _compact_alnum(full)
    compact_name = _compact_alnum(person)

    if not compact_name or compact_name not in compact_full:
        return ""

    match = re.search(re.escape(person), full, re.IGNORECASE)
    if match:
        rest = full[match.end():].strip(" ,;:-")
        if rest:
            return rest

    compact_pos = compact_full.find(compact_name)
    if compact_pos >= 0:
        tail = full
        marker = re.search(
            r"(?:Germany|Hungary|HUNGARY|GERMANY|[A-Z]{2}-\d{4,6})",
            tail,
            re.IGNORECASE,
        )
        if marker:
            return tail[marker.start():].strip(" ,;:-")

    return ""


def _get_local_value(local_result: dict, field: str) -> str:
    """Читає локальне поле з урахуванням старих назв parser."""
    aliases = {
        "supplier": ["Постачальник"],
        "supplier_address": ["Адреса постачальника", "Адреса отримувача"],
        "recipient": ["Платник"],
        "recipient_address": ["Адреса платника"],
    }

    for key in aliases.get(field, [field_map_default(field)]):
        value = str(local_result.get(key, "") or "").strip()
        if value:
            return value

    if field == "recipient":
        return str(local_result.get("Отримувач", "") or "").strip()

    return ""


def field_map_default(field: str) -> str:
    return {
        "document_type": "Тип документа",
        "document_number": "Номер документа",
        "date": "Дата",
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
    }.get(field, field)


def _reconcile_pair(field: str, ai_value: str, local_value: str) -> tuple[str, bool]:
    ai_value = str(ai_value or "").strip()
    local_value = str(local_value or "").strip()

    if local_value and not is_parser_value_sane(field, local_value):
        local_value = ""

    normalized_ai = normalize_value(field, ai_value)
    normalized_local = normalize_value(field, local_value)

    if not normalized_ai and not normalized_local:
        return "", False

    if normalized_ai and not normalized_local:
        return ai_value, False

    if normalized_local and not normalized_ai:
        return local_value, False

    if field in {"supplier", "recipient"}:
        if _values_equivalent(ai_value, local_value):
            return ai_value, False

    if field in {"supplier_address", "recipient_address", "bank_address"}:
        ai_normalized = normalize_address_for_comparison(ai_value)
        local_normalized = normalize_address_for_comparison(local_value)

        if ai_normalized == local_normalized:
            return ai_value if len(ai_value) >= len(local_value) else local_value, False

        if ai_normalized.startswith(local_normalized) or local_normalized.startswith(ai_normalized):
            return ai_value if len(ai_value) >= len(local_value) else local_value, False

    if _values_equivalent(ai_value, local_value):
        return ai_value if len(ai_value) >= len(local_value) else local_value, False

    if normalize_value(field, ai_value) == normalize_value(field, local_value):
        return ai_value if len(ai_value) >= len(local_value) else local_value, False

    return "", True


def reconcile_invoice(local_result: dict, ai_result: dict) -> dict:
    """
    Порівнює local parser та GPT без зміни ролей учасників.
    """

    fields = [
        "document_type",
        "document_number",
        "date",
        "supplier",
        "supplier_address",
        "recipient",
        "recipient_address",
        "payment_provider",
        "description",
        "quantity",
        "unit_price",
        "vat",
        "total",
        "currency",
        "iban",
        "swift",
        "bank",
        "bank_address",
    ]

    final_result = {}
    conflicts = {}

    for field in fields:
        ai_value = str(ai_result.get(field, "") or "").strip()
        local_value = _get_local_value(local_result, field)

        if field == "currency" and _is_pseudo_currency(local_value):
            local_value = ""

        if field == "total" and _is_obvious_parser_total_junk(
            local_value,
            ai_value,
            str(ai_result.get("quantity", "") or "").strip(),
            str(ai_result.get("unit_price", "") or "").strip(),
        ):
            local_value = ""

        if field == "recipient_address" and not local_value:
            payer_name = ai_result.get("recipient", "")
            old_recipient = str(local_result.get("Отримувач", "") or "").strip()
            local_value = _extract_address_after_name(old_recipient, payer_name)

        # Точкове правило для банку:
        # якщо SWIFT parser і GPT збігається, але назва банку різна,
        # залишаємо банк parser. Це захищає від Pay Set Limited
        # з блоку BILL TO при правильному WIO BANK P.J.S.C.
        if field == "bank" and local_value and ai_value:
            # Local parser may return a bank name without spaces and with
            # a trailing slash. Treat equivalent spellings as the same bank
            # and keep the clean GPT spelling.
            if _values_equivalent(ai_value, local_value):
                value = ai_value
                conflict = False
            else:
                local_swift = str(local_result.get("SWIFT", "") or "").strip().upper()
                ai_swift = str(ai_result.get("swift", "") or "").strip().upper()

                local_swift = re.sub(r"[^A-Z0-9]", "", local_swift)
                ai_swift = re.sub(r"[^A-Z0-9]", "", ai_swift)

                if (
                    local_swift
                    and ai_swift
                    and local_swift == ai_swift
                    and is_parser_value_sane("bank", local_value)
                ):
                    value = local_value
                    conflict = True
                else:
                    value, conflict = _reconcile_pair(
                        field,
                        ai_value,
                        local_value,
                    )

        elif field == "bank_address":
            # Адрес Pay Set Limited относится к реквизитам отправителя.
            # Если итоговый банк получателя определён как WIO BANK P.J.S.C.,
            # не переносим адрес чужого банка в bank_address.
            local_bank = str(local_result.get("Банк", "") or "").strip()
            ai_bank = str(ai_result.get("bank", "") or "").strip()
            local_bank_address = str(local_result.get("Адреса банку", "") or "").strip()
            ai_bank_address = str(ai_result.get("bank_address", "") or "").strip()

            pay_set = "pay set limited"
            wio_bank = "wio bank p.j.s.c."

            bank_name = (local_bank or ai_bank).lower()

            if (
                wio_bank in bank_name
                and (
                    pay_set in ai_bank.lower()
                    or pay_set in local_bank_address.lower()
                    or pay_set in ai_bank_address.lower()
                )
            ):
                value = ""
                conflict = bool(ai_bank_address or local_bank_address)
            else:
                value, conflict = _reconcile_pair(
                    field,
                    ai_value,
                    local_value,
                )
        else:
            value, conflict = _reconcile_pair(
                field,
                ai_value,
                local_value,
            )

        final_result[field] = value

        if conflict:
            conflicts[field] = {
                "parser": local_value,
                "gpt": ai_value,
            }

    return {
        "data": final_result,
        "conflicts": conflicts,
    }
