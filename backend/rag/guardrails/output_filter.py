"""Reject answers containing recognizable contact details."""
import re


_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_CURRENCY_SUFFIX = re.compile(r"^\s*(?:Ar\b|Ariary\b|MGA\b|€|\$)", re.IGNORECASE)
_PSEUDONYMOUS_BENEFICIARY_ID = re.compile(r"\bASS-[A-Z0-9]+\b", re.IGNORECASE)


def contains_sensitive_data(answer: str) -> bool:
    if _EMAIL.search(answer) or _PSEUDONYMOUS_BENEFICIARY_ID.search(answer):
        return True
    for match in _PHONE.finditer(answer):
        if len(re.sub(r"\D", "", match.group())) < 8:
            continue
        if _CURRENCY_SUFFIX.match(answer[match.end():]):
            continue
        return True
    return False
