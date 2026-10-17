"""Basic deterministic checks for obvious prompt override attempts."""
import re


_INJECTION_PATTERNS = (
    re.compile(r"\b(ignore|ignorer|oublie|forget)\b.{0,60}"
               r"\b(instruction|règle|prompt|consigne|rule)s?\b", re.I),
    re.compile(r"\b(reveal|révèle|affiche|print)\b.{0,60}"
               r"\b(system prompt|prompt système|instructions internes)\b", re.I),
    re.compile(r"\b(change|changer|switch)\b.{0,40}\b(role|rôle)\b", re.I),
)
_IDENTITY_REQUEST_PATTERNS = (
    re.compile(
        r"\b(?:nom r[eé]el|vrai nom|identit[eé])\b.{0,60}"
        r"\b(?:assur[eé]|b[eé]n[eé]ficiaire|personne)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:qui est|donne(?:-moi)?|affiche|r[eé]v[eè]le)\b.{0,60}"
        r"\b(?:assur[eé] principal|b[eé]n[eé]ficiaire)\b",
        re.I,
    ),
)
_CONTRACT_ID = re.compile(r"\bCTR-\d{6}\b", re.I)


def blocked_reason(
    question: str, contract_id: str | None = None
) -> str | None:
    if any(pattern.search(question) for pattern in _INJECTION_PATTERNS):
        return "prompt_override_attempt"
    if any(pattern.search(question) for pattern in _IDENTITY_REQUEST_PATTERNS):
        return "personal_identity_request"
    if contract_id:
        requested_contracts = {
            match.group().upper() for match in _CONTRACT_ID.finditer(question)
        }
        if any(value != contract_id.upper() for value in requested_contracts):
            return "contract_scope_mismatch"
    return None
