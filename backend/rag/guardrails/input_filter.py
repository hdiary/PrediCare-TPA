"""Basic deterministic checks for obvious prompt override attempts."""
import re


_INJECTION_PATTERNS = (
    re.compile(r"\b(ignore|ignorer|oublie|forget)\b.{0,60}"
               r"\b(instruction|règle|prompt|consigne|rule)s?\b", re.I),
    re.compile(r"\b(reveal|révèle|affiche|print)\b.{0,60}"
               r"\b(system prompt|prompt système|instructions internes)\b", re.I),
    re.compile(r"\b(change|changer|switch)\b.{0,40}\b(role|rôle)\b", re.I),
    re.compile(
        r"\b(?:r[eé]p[eè]te|r[eé]v[eè]le|affiche|montre|liste|traduis|"
        r"traduire|repeat|reveal|show|list|translate|summari[sz]e)\b"
        r".{0,100}\b(?:instructions?|r[eè]gles?|consignes?|"
        r"prompt(?:\s+syst[eè]me)?|system prompt|developer instructions?)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:instructions?|r[eè]gles?|consignes?)\b.{0,100}"
        r"\b(?:re[cç]ues?\s+(?:au\s+d[eé]but|initialement)|"
        r"received\s+at\s+the\s+beginning|exactes?\s+que\s+tu\s+dois\s+suivre|"
        r"you\s+(?:were\s+)?given|mot\s+pour\s+mot|word\s+for\s+word)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:encode|encod[eé]|compl[eè]te|complete|reformule|r[eé]sume|"
        r"summarize|summarise)\b.{0,80}\b(?:ton|your|le|the)?\s*"
        r"(?:system\s+prompt|prompt\s+syst[eè]me|instructions?)\b",
        re.I,
    ),
    re.compile(r"\b(?:base64|rot13)\b", re.I),
    re.compile(
        r"\b(?:what\s+is|quel(?:le)?s?\s+sont|show|affiche|montre)\b"
        r".{0,50}\b(?:your\s+)?(?:system\s+prompt|prompt\s+syst[eè]me)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:prompt\s+syst[eè]me|system\s+prompt)\b.{0,80}"
        r"\b(?:commence\s+par|starts?\s+with|compl[eè]te|complete)\b"
        r"|\b(?:compl[eè]te|complete)\b.{0,60}"
        r"\b(?:phrase|sentence)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:voici|here\s+is)\s+(?:mon|my)\s+prompt\b"
        r"|\b(?:assistant|human)\s*:\s*.{0,100}"
        r"\b(?:voici|here\s+is)\b.{0,40}\bprompt\b",
        re.I,
    ),
    re.compile(
        r"\b(?:tu\s+es\s+maintenant|you\s+are\s+now|passe\s+en\s+mode|"
        r"switch\s+to)\b.{0,50}\b(?:administrateur|administrator|"
        r"d[eé]veloppeur|developer\s+mode|DAN|sans\s+restrictions)\b"
        r"|\bdo\s+anything\s+now\b",
        re.I,
    ),
    re.compile(
        r"\b(?:developer\s+mode|mode\s+d[eé]veloppeur|"
        r"restrictions?\s+d[eé]sactiv[eé]es?|r[eé]ponds?\s+à\s+"
        r"(?:toutes?|n'importe\s+quelles?)\s+(?:mes\s+)?questions?)\b"
        r"|\bDAN\b",
        re.I,
    ),
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
    re.compile(
        r"\b(?:date\s+de\s+naissance|ann[eé]e\s+de\s+naissance|"
        r"sexe)\b.{0,80}\b(?:assur[eé]|b[eé]n[eé]ficiaire|conjoint|"
        r"enfant)\b|\b(?:assur[eé]s?|b[eé]n[eé]ficiaires?|conjoint|"
        r"enfants?)\b.{0,80}\b(?:sexe|ann[eé]e\s+de\s+naissance|"
        r"date\s+de\s+naissance)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:adresse|domicile|t[eé]l[eé]phone|num[eé]ro\s+de\s+"
        r"t[eé]l[eé]phone|coordonn[eé]es)\b.{0,80}"
        r"\b(?:assur[eé]|b[eé]n[eé]ficiaire|souscripteur|ASS-[A-Z0-9]+)\b"
        r"|\b(?:assur[eé]|b[eé]n[eé]ficiaire|souscripteur|ASS-[A-Z0-9]+)\b"
        r".{0,80}\b(?:adresse|domicile|t[eé]l[eé]phone|coordonn[eé]es)\b",
        re.I,
    ),
    re.compile(
        r"\bASS-[A-Z0-9]+\b.{0,80}\b(?:nom complet|identit[eé]|"
        r"coordonn[eé]es|adresse|t[eé]l[eé]phone)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:combien|nombre)\b.{0,60}\b(?:enfants?|b[eé]n[eé]ficiaires?)\b"
        r".{0,40}\b(?:moins\s+de|âg[eé]s?\s+de|under\s+\d+)\b",
        re.I,
    ),
)
_RESTRICTED_AGGREGATE_PATTERNS = (
    re.compile(
        r"\b(?:liste|affiche|donne|montre|compare)\b.{0,80}"
        r"\b(?:tous les contrats|tous les prestataires|"
        r"toutes les fraudes|fraudes?\s+(?:dans|de)\s+la\s+base|"
        r"base de donn[eé]es)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:combien|nombre)\b.{0,50}\bfraudes?\b"
        r"|\b(?:liste|affiche|donne|montre)\b.{0,60}"
        r"\bprestataires?\b.{0,40}\b(?:suspect|fraude)\b",
        re.I,
    ),
)
_MEDICAL_ADVICE = re.compile(
    r"\b(?:quel(?:le)?s?\s+m[eé]dicament|que\s+dois-je\s+prendre|"
    r"que\s+me\s+conseilles-tu)\b|"
    r"\b(?:diagnostique|prescris|recommande)\b.{0,50}"
    r"\b(?:m[eé]dicament|traitement|dose)\b",
    re.I,
)
_LEGAL_ADVICE = re.compile(
    r"\b(?:poursuivre|attaquer)\b.{0,60}\b(?:justice|tribunal|en\s+justice)\b"
    r"|\bavis\s+juridique\b|\bdois-je\s+porter\s+plainte\b",
    re.I,
)
_OUT_OF_SCOPE = re.compile(
    r"\b(?:recette|comment\s+cuisiner|tarte\s+tatin)\b"
    r"|\b(?:pour\s+qui\s+dois-je\s+voter|candidat(?:e)?|"
    r"prochaines?\s+[eé]lections?)\b",
    re.I,
)
_CONTRACT_ID = re.compile(r"\bCTR-\d{6}\b", re.I)
_SYSTEM_TAG = re.compile(r"<system\b[^>]*>.*?</system\s*>", re.I | re.S)
_TOKEN_SYSTEM_BLOCK = re.compile(
    r"<\|im_start\|>\s*system\b.*?<\|im_end\|>", re.I | re.S)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _is_injection_segment(segment: str) -> bool:
    return any(pattern.search(segment) for pattern in _INJECTION_PATTERNS)


def sanitize_question(question: str) -> tuple[str, bool]:
    """Remove isolated injection payloads while preserving legitimate questions."""
    text = question
    removed_payload = False
    for pattern in (_TOKEN_SYSTEM_BLOCK, _SYSTEM_TAG, _HTML_COMMENT):
        text, count = pattern.subn("\n", text)
        removed_payload = removed_payload or count > 0
    text = re.sub(
        r"\*{1,3}(?:IMPORTANT|FIN)\*{1,3}|#{1,6}\s*FIN DU PROMPT\s*#*",
        "\n",
        text,
        flags=re.I,
    )
    text = re.sub(r"</?system\s*>", "\n", text, flags=re.I)
    text = re.sub(r"\[(?:syst[eè]me|system)\]", "\n", text, flags=re.I)
    segments = re.split(r"(?<=[.!?])\s+|[\r\n]+", text)
    safe_segments = []
    for segment in segments:
        segment = re.sub(r"^[\s.*#:_-]+", "", segment.strip())
        if not segment:
            continue
        if _is_injection_segment(segment):
            removed_payload = True
        else:
            safe_segments.append(segment)
    sanitized = " ".join(safe_segments).strip()
    return sanitized, removed_payload and not sanitized


def blocked_reason(
    question: str, contract_id: str | None = None
) -> str | None:
    if any(pattern.search(question) for pattern in _INJECTION_PATTERNS):
        return "prompt_override_attempt"
    if any(pattern.search(question) for pattern in _IDENTITY_REQUEST_PATTERNS):
        return "personal_identity_request"
    if any(
        pattern.search(question) for pattern in _RESTRICTED_AGGREGATE_PATTERNS
    ):
        return "restricted_aggregate_request"
    if _MEDICAL_ADVICE.search(question):
        return "medical_advice_request"
    if _LEGAL_ADVICE.search(question):
        return "legal_advice_request"
    if _OUT_OF_SCOPE.search(question):
        return "out_of_scope_request"
    if contract_id:
        requested_contracts = {
            match.group().upper() for match in _CONTRACT_ID.finditer(question)
        }
        if any(value != contract_id.upper() for value in requested_contracts):
            return "contract_scope_mismatch"
    return None
