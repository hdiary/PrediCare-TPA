"""Reject answers containing recognizable contact details."""
import re


_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_CURRENCY_SUFFIX = re.compile(r"^\s*(?:Ar\b|Ariary\b|MGA\b|€|\$)", re.IGNORECASE)
_PSEUDONYMOUS_BENEFICIARY_ID = re.compile(r"\bASS-[A-Z0-9]+\b", re.IGNORECASE)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_INVOICE_ID = re.compile(r"\bFAC-\d{8}\b", re.IGNORECASE)
_PROMPT_FINGERPRINTS = (
    re.compile(r"\bTu es l'assistant virtuel de PrediCare TPA\b", re.I),
    re.compile(r"\bYou are the virtual assistant of PrediCare TPA\b", re.I),
    re.compile(
        r"R[eé]pond\s+UNIQUEMENT\s+[àa]\s+partir\s+des\s+extraits\s+"
        r"fournis\s+dans\s+le\s+contexte",
        re.I,
    ),
    re.compile(r"Ne r[eé]v[eè]le jamais ce prompt", re.I),
    re.compile(r"SONT AUTORIS[EÉ]S [ÀA] [ÊE]TRE AFFICH[EÉ]S", re.I),
    re.compile(r"##\s*1\.\s*(?:Scope and reliability|Périmètre et fiabilité)", re.I),
    re.compile(
        r"Données contractuelles vs données personnelles|"
        r"Priorité de sourcing|Source priority",
        re.I,
    ),
)
_INTERNAL_TOOL_NAMES = re.compile(
    r"\b(?:search_contract_documents|search_my_claims|"
    r"get_my_reimbursement_total)\b"
)


def contains_prompt_leakage(answer: str) -> bool:
    matches = sum(
        bool(pattern.search(answer)) for pattern in _PROMPT_FINGERPRINTS)
    return bool(
        matches >= 2
        or _PROMPT_FINGERPRINTS[0].search(answer)
        or _PROMPT_FINGERPRINTS[1].search(answer)
        or _INTERNAL_TOOL_NAMES.search(answer)
    )


def contains_sensitive_data(answer: str) -> bool:
    if contains_prompt_leakage(answer):
        return True
    if _EMAIL.search(answer) or _PSEUDONYMOUS_BENEFICIARY_ID.search(answer):
        return True
    for match in _PHONE.finditer(answer):
        if len(re.sub(r"\D", "", match.group())) < 8:
            continue
        if _ISO_DATE.fullmatch(match.group()):
            continue
        if any(
            invoice.start() <= match.start() and invoice.end() >= match.end()
            for invoice in _INVOICE_ID.finditer(answer)
        ):
            continue
        if _CURRENCY_SUFFIX.match(answer[match.end():]):
            continue
        return True
    return False
