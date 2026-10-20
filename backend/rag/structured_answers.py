"""Deterministic answers for category rows in the coverage table."""
import re

from rag.retriever import RetrievedChunk


_CATEGORY_PATTERNS = (
    r"dentaire?",
    r"pharmacie",
    r"laboratoire",
    r"imagerie",
    r"hospitalisation",
    r"maternit[eé]",
    r"optique",
    r"kin[eé]sith[eé]rapie",
    r"consultation",
)
_TABLE_QUESTION = re.compile(
    r"\b(?:taux|pourcentage|remboursement|plafond|carence|franchise|"
    r"garantie|garanties|couvert(?:e|es|s)?|prise en charge)\b",
    re.IGNORECASE,
)
_GENERAL_GUARANTEE_QUESTION = re.compile(
    r"\b(?:quelles?\s+sont|liste|r[eé]capitul(?:e|er|atif)|"
    r"principales?)\b.{0,60}\bgaranties?\b|\bgaranties?\s+principales?\b",
    re.IGNORECASE,
)
_EXCLUSION_QUESTION = re.compile(r"\bexclusions?\b", re.IGNORECASE)
_GLOBAL_CEILING_QUESTION = re.compile(
    r"\bplafond\b.*\bglobal\b|\bglobal\b.*\bplafond\b",
    re.IGNORECASE,
)
_BENEFICIARY_QUESTION = re.compile(r"\bb[eé]n[eé]ficiaires?\b", re.IGNORECASE)
_BENEFICIARY_ROW = re.compile(
    r"\bASS-[A-Z0-9]+\s+"
    r"(?P<role>ASSURE_PRINCIPAL|CONJOINT|ENFANT)\b",
    re.IGNORECASE,
)
_GLOBAL_CEILING = re.compile(
    r"Plafond annuel global(?: par bénéficiaire)?\s*:\s*"
    r"(?P<amount>\d[\d .]*\s*(?:Ar|MGA))",
    re.IGNORECASE,
)
_POLICY_NUMBER = re.compile(r"\bPolice\s+(?P<number>POL-[A-Z0-9-]+)\b", re.I)
_POLICY_NUMBER_QUESTION = re.compile(
    r"\b(?:num[eé]ro|r[eé]f[eé]rence)\b.*\bpolice\b|\bpolice\b.*"
    r"\b(?:num[eé]ro|r[eé]f[eé]rence)\b",
    re.IGNORECASE,
)
_ANNUAL_PREMIUM_QUESTION = re.compile(
    r"\b(?:prime(?:\s+annuelle)?|cotisation(?:\s+annuelle)?)\b",
    re.IGNORECASE,
)
_SUBSCRIBER_QUESTION = re.compile(
    r"\b(?:nom|raison\s+sociale)\b.{0,40}\bsouscripteur\b|"
    r"\bsouscripteur\b.{0,40}\b(?:nom|raison\s+sociale)\b|"
    r"\bqui\s+est\s+le\s+souscripteur\b",
    re.IGNORECASE,
)
_CONTRACT_STATUS_QUESTION = re.compile(
    r"\bstatut\b.{0,30}\bcontrat\b|\bcontrat\b.{0,30}\bstatut\b",
    re.IGNORECASE,
)
_CONTRACT_END_DATE_QUESTION = re.compile(
    r"\b(?:date\s+de\s+fin|fin\s+de\s+mon\s+contrat)\b",
    re.IGNORECASE,
)
_CONTRACT_EFFECTIVE_DATE_QUESTION = re.compile(
    r"\bdate\s+d['’]effet\b.{0,40}\b(?:police|contrat)\b"
    r"|\b(?:police|contrat)\b.{0,40}\bdate\s+d['’]effet\b",
    re.IGNORECASE,
)
_ANNUAL_PREMIUM = re.compile(
    r"Prime annuelle\s*:\s*(?P<per_beneficiary>[\d ]+?)\s*Ar\s+"
    r"par bénéficiaire,\s+soit\s+(?P<total>[\d ]+?)\s*Ar\s+pour\s+"
    r"(?P<count>\d+)\s+bénéficiaire(?:\(s\)|s)?",
    re.IGNORECASE,
)
_SUBSCRIBER = re.compile(
    r"Souscripteur\s*:\s*(?P<name>.+?)\s+Date d'effet",
    re.IGNORECASE,
)
_INDIVIDUAL_SUBSCRIBER = re.compile(
    r"^Adh[eé]sion individuelle(?:\s+\(Particulier\))?$",
    re.IGNORECASE,
)
_LEGAL_ENTITY_SUBSCRIBER = re.compile(
    r"^(?P<name>.+?\b(?:SAS|SARL|SARLU|SA|SNC|SCS|SCA|EURL)\b)"
    r"(?:\s*\([^)]*\))?$",
    re.IGNORECASE,
)
_CONTRACT_STATUS = re.compile(
    r"\bStatut\s*:\s*(?P<status>ACTIF|RESILIE)\b", re.IGNORECASE
)
_CONTRACT_END_DATE = re.compile(
    r"\bFin\s*:\s*(?P<date>\d{4}-\d{2}-\d{2})\b", re.IGNORECASE
)
_CONTRACT_EFFECTIVE_DATE = re.compile(
    r"\bDate\s+d['’]effet\s+(?:de\s+la\s+)?(?:police|contrat)\s*:\s*"
    r"(?P<date>\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)
_COVERAGE_ROW = re.compile(
    r"(?P<category>dentaire?|pharmacie|laboratoire|imagerie|"
    r"hospitalisation|maternit[eé]|optique|kin[eé]sith[eé]rapie|"
    r"consultation)\s+"
    r"(?P<rate>\d{1,3}\s*%)\s+"
    r"(?P<ceiling>\d[\d .]*\s*(?:Ar|MGA))\s+"
    r"(?P<deductible>aucune|[\d .]+\s*(?:Ar|MGA))\s+"
    r"(?P<waiting>aucune|\d+\s+jours?)",
    re.IGNORECASE,
)
_CATEGORY_MATCHERS = tuple(
    (re.compile(rf"\b(?:{pattern})\b", re.IGNORECASE), pattern)
    for pattern in _CATEGORY_PATTERNS
)
_CATEGORY_LABELS = {
    "maternite": "maternité",
    "kinesitherapie": "kinésithérapie",
}
_CATEGORY_SYNONYMS = (
    (re.compile(r"\b(?:m[eé]decin(?:e)?\s+g[eé]n[eé]ral(?:iste)?|"
                r"g[eé]n[eé]raliste)\b", re.I), "consultation"),
)


def _category_label(category: str) -> str:
    return _CATEGORY_LABELS.get(category.casefold(), category.casefold())


def is_guarantee_table_question(question: str) -> bool:
    return bool(
        _TABLE_QUESTION.search(question)
    )


def answer_from_guarantee_table(
    question: str, chunks: list[RetrievedChunk]
) -> tuple[str, RetrievedChunk] | None:
    if not is_guarantee_table_question(question):
        return None

    requested_category = next((
        category
        for pattern, category in _CATEGORY_MATCHERS
        if pattern.search(question)
    ), None)
    if requested_category is None:
        requested_category = next(
            (category for pattern, category in _CATEGORY_SYNONYMS
             if pattern.search(question)),
            None,
        )
    for chunk in chunks:
        if not chunk.article or "article 5" not in chunk.article.casefold():
            continue
        rows = list(_COVERAGE_ROW.finditer(chunk.content))
        if requested_category:
            rows = [
                row for row in rows
                if re.fullmatch(
                    requested_category, row.group("category"), re.IGNORECASE)
            ]
        if requested_category and rows:
            row = rows[0]
            answer = (
                f"Pour la catégorie "
                f"{_category_label(row.group('category'))}, le taux "
                f"de remboursement est de {row.group('rate')}. Le plafond "
                f"annuel est de {row.group('ceiling')}, la franchise est "
                f"{row.group('deductible').lower()} et le délai de carence "
                f"est de {row.group('waiting').lower()}."
            )
            return answer, chunk
        if not requested_category and rows and _GENERAL_GUARANTEE_QUESTION.search(question):
            answer_lines = ["Les principales garanties de votre formule sont :"]
            global_ceiling = _GLOBAL_CEILING.search(chunk.content)
            if global_ceiling:
                answer_lines.append(
                    f"Plafond annuel global par bénéficiaire : "
                    f"{global_ceiling.group('amount')}."
                )
            answer_lines.extend(
                f"- {_category_label(row.group('category')).capitalize()} : "
                f"{row.group('rate')}, plafond annuel "
                f"{row.group('ceiling')}, franchise "
                f"{row.group('deductible').lower()}, carence "
                f"{row.group('waiting').lower()}."
                for row in rows
            )
            return "\n".join(answer_lines), chunk
        if not requested_category and not _GLOBAL_CEILING_QUESTION.search(question):
            return (
                "Le tableau des garanties ne précise pas de ligne ni de "
                "plafond distinct pour cette catégorie. Veuillez contacter "
                "un gestionnaire pour confirmer sa prise en charge.",
                chunk,
            )
    return None


def answer_from_contract(
    question: str, chunks: list[RetrievedChunk]
) -> tuple[str, RetrievedChunk] | None:
    contract_chunks = [chunk for chunk in chunks if chunk.scope == "contract"]

    if _ANNUAL_PREMIUM_QUESTION.search(question):
        for chunk in contract_chunks:
            match = _ANNUAL_PREMIUM.search(chunk.content)
            if match:
                per_beneficiary = " ".join(
                    match.group("per_beneficiary").split())
                total = " ".join(match.group("total").split())
                count = match.group("count")
                answer = (
                    f"La prime annuelle est de {per_beneficiary} Ar par "
                    f"bénéficiaire, soit {total} Ar pour {count} "
                    f"bénéficiaire{'s' if count != '1' else ''}."
                )
                return answer, chunk

    if _SUBSCRIBER_QUESTION.search(question):
        for chunk in contract_chunks:
            match = _SUBSCRIBER.search(chunk.content)
            if not match:
                continue
            name = match.group("name").strip()
            if _INDIVIDUAL_SUBSCRIBER.fullmatch(name):
                return "Le souscripteur est une adhésion individuelle.", chunk
            entity = _LEGAL_ENTITY_SUBSCRIBER.fullmatch(name)
            if entity:
                return f"Le souscripteur est {entity.group('name')}.", chunk

    if _CONTRACT_STATUS_QUESTION.search(question):
        for chunk in contract_chunks:
            match = _CONTRACT_STATUS.search(chunk.content)
            if match:
                return (
                    f"Le statut de votre contrat est "
                    f"{match.group('status').upper()}.",
                    chunk,
                )

    if _CONTRACT_END_DATE_QUESTION.search(question):
        for chunk in contract_chunks:
            match = _CONTRACT_END_DATE.search(chunk.content)
            if match:
                return (
                    f"La date de fin de votre contrat est "
                    f"{match.group('date')}.",
                    chunk,
                )

    if _CONTRACT_EFFECTIVE_DATE_QUESTION.search(question):
        for chunk in contract_chunks:
            match = _CONTRACT_EFFECTIVE_DATE.search(chunk.content)
            if match:
                return (
                    f"La date d'effet de votre contrat est "
                    f"{match.group('date')}.",
                    chunk,
                )

    if _EXCLUSION_QUESTION.search(question):
        for chunk in chunks:
            if not chunk.article or not chunk.article.casefold().startswith(
                "article 10"
            ):
                continue
            body = chunk.content.split("] ", 1)[-1]
            items = [
                item.strip()
                for item in body.split("\x7f")
                if item.strip() and not item.strip().startswith("DOCUMENT FICTIF")
            ]
            if items:
                answer = "Les exclusions principales de votre formule sont :\n"
                answer += "\n".join(
                    f"- {item.rstrip(' .')}." for item in items
                )
                return answer, chunk

    if _BENEFICIARY_QUESTION.search(question):
        for chunk in contract_chunks:
            roles = [
                match.group("role").upper()
                for match in _BENEFICIARY_ROW.finditer(chunk.content)
            ]
            if not roles:
                continue
            labels = {
                "ASSURE_PRINCIPAL": "assuré principal",
                "CONJOINT": "conjoint",
                "ENFANT": "enfant",
            }
            counts = {role: roles.count(role) for role in labels}
            categories = [
                f"{count} {labels[role]}" + ("s" if count > 1 else "")
                for role, count in counts.items() if count
            ]
            answer = (
                "Les conditions particulières indiquent : "
                f"{', '.join(categories)}. "
                "Les identifiants individuels ne sont pas affichés."
            )
            return answer, chunk

    if _GLOBAL_CEILING_QUESTION.search(question):
        for chunk in contract_chunks:
            match = _GLOBAL_CEILING.search(chunk.content)
            if match:
                answer = (
                    "Le plafond annuel global de votre contrat est de "
                    f"{match.group('amount')} par bénéficiaire."
                )
                return answer, chunk

    if _POLICY_NUMBER_QUESTION.search(question):
        for chunk in contract_chunks:
            match = _POLICY_NUMBER.search(chunk.content)
            if match:
                return (
                    f"Le numéro de police de votre contrat est "
                    f"{match.group('number')}.",
                    chunk,
                )
    return None


def is_exclusion_question(question: str) -> bool:
    return bool(_EXCLUSION_QUESTION.search(question))


def is_direct_contract_question(question: str) -> bool:
    return bool(
        _BENEFICIARY_QUESTION.search(question)
        or _GLOBAL_CEILING_QUESTION.search(question)
        or _POLICY_NUMBER_QUESTION.search(question)
        or _ANNUAL_PREMIUM_QUESTION.search(question)
        or _SUBSCRIBER_QUESTION.search(question)
        or _CONTRACT_STATUS_QUESTION.search(question)
        or _CONTRACT_END_DATE_QUESTION.search(question)
        or _CONTRACT_EFFECTIVE_DATE_QUESTION.search(question)
    )
