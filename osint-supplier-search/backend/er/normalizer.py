from __future__ import annotations
import re
import unicodedata
import phonenumbers
import tldextract
import pycountry
from transliterate import translit, get_available_language_codes

# Legal suffixes to strip from company names
_LEGAL_SUFFIXES = re.compile(
    r"\b(LLC|LTD|LIMITED|INC|CORP|CORPORATION|GMBH|AG|SA|SAS|BV|NV|PLC|"
    r"OOO|ZAO|OAO|AO|PAO|ООО|ЗАО|ОАО|АО|ПАО|"
    r"CO\.?|COMPANY|GROUP|HOLDING|HOLDINGS|INTERNATIONAL|INTL)\b\.?",
    re.IGNORECASE,
)
_WHITESPACE = re.compile(r"\s+")


def normalize_name(name: str | None) -> str:
    if not name:
        return ""
    # Transliterate non-Latin scripts to Latin
    result = name
    for lang in get_available_language_codes():
        try:
            result = translit(result, lang, reversed=True)
        except Exception:
            pass
    # NFKC unicode normalize
    result = unicodedata.normalize("NFKC", result)
    # Strip legal suffixes
    result = _LEGAL_SUFFIXES.sub("", result)
    # Remove punctuation except spaces
    result = re.sub(r"[^\w\s]", " ", result)
    # Collapse whitespace, uppercase
    result = _WHITESPACE.sub(" ", result).strip().upper()
    return result


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    try:
        parsed = phonenumbers.parse(phone, None)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        pass
    return None


def normalize_website(url: str | None) -> str | None:
    if not url:
        return None
    extracted = tldextract.extract(url)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}".lower()
    return None


def normalize_country(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    if len(raw) == 2:
        return raw.upper()
    try:
        country = pycountry.countries.lookup(raw)
        return country.alpha_2
    except LookupError:
        return raw.upper()[:2]


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    email = email.strip().lower()
    # Basic validation
    if "@" in email and "." in email.split("@")[-1]:
        return email
    return None
