"""Allow-listed, parameterized tools available to the RAG agent."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from rag.embeddings import EmbeddingClient
from rag.retriever import ContractRetriever, RetrievedChunk


_ASSURED_ID = re.compile(r"^ASS-[0-9A-F]{10}$", re.IGNORECASE)
_INVOICE_ID = re.compile(r"^FAC-[0-9]{8}$", re.IGNORECASE)
_PSEUDONYMOUS_ID = re.compile(r"\bASS-[A-Z0-9]+\b", re.IGNORECASE)
_CLAIM_SELF_REFERENCE = re.compile(
    r"\b(?:mon|ma|mes)\b(?:\s+\w+){0,2}\s+\b(?:dossiers?|factures?)\b"
    r"|\b(?:dossiers?|factures?)\b(?:\s+\w+){0,2}\s+\b(?:mon|ma|mes)\b"
    r"|\bmes\s+remboursements?\b"
    r"|m['’](?:a|ont)-t-on\s+rembours\w*",
    re.IGNORECASE)
_CLAIM_FILTER = re.compile(
    r"\bFAC-[0-9]{8}\b"
    r"|\b[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}\b"
    r"|\b[0-9]{1,2}[/-][0-9]{1,2}(?:[/-][0-9]{2,4})?\b"
    r"|\b[0-9]{1,2}\s+(?:janvier|f[eé]vrier|mars|avril|mai|juin|"
    r"juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)\b",
    re.IGNORECASE)
_CLAIM_STATUS_QUESTION = re.compile(
    r"\b(?:o[uù] en (?:est|sont)|statut|avancement|suivi)\b",
    re.IGNORECASE)
_CLAIM_LIST_QUESTION = re.compile(
    r"\b(?:liste|historique|derni[eè]res?|r[eé]centes?)\b",
    re.IGNORECASE)
_REIMBURSEMENT_TOTAL_QUESTION = re.compile(
    r"\b(?:combien|total|montant total)\b.{0,60}"
    r"\b(?:rembours\w*|pris en charge)\b",
    re.IGNORECASE)
_CLAIM_STATUS_LABELS = {
    "PAYEE": "Payée",
    "REJETEE": "Non prise en charge",
    "EN_COURS": "En cours de traitement",
}
_CLAIM_TOOL = {
    "type": "function",
    "function": {
        "name": "search_my_claims",
        "description": (
            "Consulter le statut et les dates des factures de l'assuré "
            "connecté, ainsi que le montant facturé et le montant pris en "
            "charge. Les dates filtrent aussi bien la date de soin que la "
            "date de réception. Pour une date précise, fournir date_from et "
            "date_to identiques. Pour retrouver ses dossiers récents, ne "
            "fournir aucun filtre."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "date_from": {
                    "type": ["string", "null"],
                    "description": (
                        "Date minimale (date de soin ou de réception), "
                        "au format AAAA-MM-JJ."
                    ),
                },
                "date_to": {
                    "type": ["string", "null"],
                    "description": (
                        "Date maximale (date de soin ou de réception), "
                        "au format AAAA-MM-JJ."
                    ),
                },
                "invoice_id": {
                    "type": ["string", "null"],
                    "description": "Identifiant de facture FAC- suivi de 8 chiffres.",
                },
            },
            "required": ["date_from", "date_to", "invoice_id"],
            "additionalProperties": False,
        },
    },
}
_REIMBURSEMENT_TOTAL_TOOL = {
    "type": "function",
    "function": {
        "name": "get_my_reimbursement_total",
        "description": (
            "Calculer le total historique, sans limite de nombre de factures, "
            "des montants pris en charge pour les factures PAYEE de l'assuré "
            "connecté. Ne pas utiliser la liste des 10 factures récentes pour "
            "répondre à une question de total."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
}
_PROVIDER_CLAIM_TOOL = {
    "type": "function",
    "function": {
        "name": "search_my_claims",
        "description": (
            "Consulter les factures du professionnel de santé connecté "
            "uniquement. La recherche est limitée côté serveur à son "
            "prestataire_id. Utiliser pour le statut, les dates et les "
            "montants de ses factures."
        ),
        "strict": True,
        "parameters": _CLAIM_TOOL["function"]["parameters"],
    },
}
_DOCUMENT_TOOL = {
    "type": "function",
    "function": {
        "name": "search_contract_documents",
        "description": (
            "Rechercher des extraits sourcés dans les conditions particulières, "
            "conditions générales, barèmes et guides du contrat connecté."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Question ou termes à chercher dans les documents.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}
_NETWORK_DOCUMENT_TOOL = {
    "type": "function",
    "function": {
        "name": "search_network_documents",
        "description": (
            "Rechercher des extraits sourcés uniquement dans les documents "
            "généraux du réseau de soins. Ne recherche jamais dans les "
            "documents propres au contrat d'un assuré."
        ),
        "strict": True,
        "parameters": _DOCUMENT_TOOL["function"]["parameters"],
    },
}
_CLAIMS_SQL = text("""
    SELECT facture_id, date_reception, date_soin, date_traitement,
           type_facture, montant_total, montant_pris_en_charge, statut
    FROM v_agent_claim_status
    WHERE assure_id = :assure_id
      AND contrat_id = :contract_id
      AND (
          (
              (CAST(:date_from AS date) IS NULL
               OR date_reception >= CAST(:date_from AS date))
              AND
              (CAST(:date_to AS date) IS NULL
               OR date_reception <= CAST(:date_to AS date))
          )
          OR
          (
              (CAST(:date_from AS date) IS NULL
               OR date_soin >= CAST(:date_from AS date))
              AND
              (CAST(:date_to AS date) IS NULL
               OR date_soin <= CAST(:date_to AS date))
          )
      )
      AND (
          CAST(:invoice_id AS text) IS NULL
          OR facture_id = CAST(:invoice_id AS text)
      )
    ORDER BY date_reception DESC NULLS LAST, facture_id
    LIMIT 10
""")
_REIMBURSEMENT_TOTAL_SQL = text("""
    SELECT COALESCE(SUM(montant_pris_en_charge), 0) AS total_rembourse,
           COUNT(*) AS nombre_factures_payees
    FROM v_agent_claim_status
    WHERE assure_id = :assure_id
      AND contrat_id = :contract_id
      AND statut = 'PAYEE'
""")
_PROVIDER_CLAIMS_SQL = text("""
    SELECT facture_id, date_reception, date_soin, date_traitement,
           type_facture, montant_total, montant_pris_en_charge, statut
    FROM v_agent_claim_status
    WHERE prestataire_id = :prestataire_id
      AND (
          (
              (CAST(:date_from AS date) IS NULL
               OR date_reception >= CAST(:date_from AS date))
              AND
              (CAST(:date_to AS date) IS NULL
               OR date_reception <= CAST(:date_to AS date))
          )
          OR
          (
              (CAST(:date_from AS date) IS NULL
               OR date_soin >= CAST(:date_from AS date))
              AND
              (CAST(:date_to AS date) IS NULL
               OR date_soin <= CAST(:date_to AS date))
          )
      )
      AND (
          CAST(:invoice_id AS text) IS NULL
          OR facture_id = CAST(:invoice_id AS text)
      )
    ORDER BY date_reception DESC NULLS LAST, facture_id
    LIMIT 10
""")


@dataclass(frozen=True)
class ToolOutput:
    content: str
    sources: list[RetrievedChunk]
    claims: list[dict[str, Any]] | None = None
    aggregate: dict[str, Any] | None = None


class AgentToolkit:
    def __init__(
        self,
        *,
        embeddings: EmbeddingClient,
        retriever: ContractRetriever,
        engine: Engine,
        contract_id: str,
        assure_id: str | None,
        prestataire_id: str | None = None,
    ):
        if assure_id and not _ASSURED_ID.fullmatch(assure_id):
            raise ValueError("assure_id must be a pseudonymous ASS- identifier")
        if prestataire_id and not re.fullmatch(
                r"PRE-[0-9]{5}", prestataire_id, re.IGNORECASE):
            raise ValueError(
                "prestataire_id must be a pseudonymous PRE- identifier")
        if assure_id and prestataire_id:
            raise ValueError("Only one authenticated claim scope is allowed")
        self.embeddings = embeddings
        self.retriever = retriever
        self.engine = engine
        self.contract_id = contract_id
        self.assure_id = assure_id.upper() if assure_id else None
        self.prestataire_id = (
            prestataire_id.upper() if prestataire_id else None)

    @property
    def definitions(self) -> list[dict[str, Any]]:
        if self.prestataire_id:
            return [_NETWORK_DOCUMENT_TOOL, _PROVIDER_CLAIM_TOOL]
        tools = [_DOCUMENT_TOOL]
        if self.assure_id:
            tools.append(_CLAIM_TOOL)
            tools.append(_REIMBURSEMENT_TOTAL_TOOL)
        return tools

    @staticmethod
    def is_claim_question(question: str) -> bool:
        return bool(
            _CLAIM_SELF_REFERENCE.search(question)
            or _REIMBURSEMENT_TOTAL_QUESTION.search(question))

    @staticmethod
    def is_reimbursement_total_question(question: str) -> bool:
        return bool(_REIMBURSEMENT_TOTAL_QUESTION.search(question))

    @staticmethod
    def is_claim_status_question(question: str) -> bool:
        if (not AgentToolkit.is_claim_question(question)
                or _CLAIM_FILTER.search(question)
                or _REIMBURSEMENT_TOTAL_QUESTION.search(question)):
            return False
        return bool(
            _CLAIM_STATUS_QUESTION.search(question)
            or _CLAIM_LIST_QUESTION.search(question)
        )

    def recent_claims_answer(self) -> str:
        result = self.execute("search_my_claims", {
            "date_from": None,
            "date_to": None,
            "invoice_id": None,
        })
        claims = result.claims
        if claims is None:
            raise RuntimeError(
                "Claim search did not return structured claim results")
        if not claims:
            return "Aucune facture correspondante trouvée pour votre compte."

        lines = [
            f"Voici les factures les plus récentes "
            f"{'de votre activité' if self.prestataire_id else 'de votre compte'} "
            f"({len(claims)} résultat(s)) :"
        ]
        for claim in claims:
            invoice_type = (claim["type_facture"] or "").replace(
                "_", " ").capitalize()
            details = [invoice_type] if invoice_type else []
            if claim["date_soin"]:
                details.append(
                    "soin le " + self._display_date(claim["date_soin"]))
            if claim["date_reception"]:
                details.append(
                    "reçue le "
                    f"{self._display_date(claim['date_reception'])}")
            if claim["date_traitement"]:
                details.append(
                    "traitée le "
                    f"{self._display_date(claim['date_traitement'])}")
            details.append(
                f"montant facturé {self._format_amount(claim['montant_total'])}")
            details.append(
                "montant pris en charge "
                f"{self._format_amount(claim['montant_pris_en_charge'])}")
            details.append(f"statut {claim['statut']}")
            lines.append(f"- **{claim['facture_id']}** : " +
                         ", ".join(details))
        return "\n".join(lines)

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolOutput:
        if name in {"search_contract_documents", "search_network_documents"}:
            if name == "search_contract_documents" and self.prestataire_id:
                raise ValueError(
                    "Providers may only search network-wide documents")
            if name == "search_network_documents" and not self.prestataire_id:
                raise ValueError(
                    "search_network_documents requires a provider context")
            self._require_arguments(arguments, {"query"})
            query = arguments["query"]
            if not isinstance(query, str) or not query.strip():
                raise ValueError("query must be a non-empty string")
            embedding = self.embeddings.embed([query])[0]
            if name == "search_network_documents":
                chunks = self.retriever.search_global(embedding)
            else:
                chunks = self.retriever.search(embedding, self.contract_id)
            if not chunks:
                return ToolOutput(
                    "Aucun extrait pertinent trouvé dans les documents du "
                    "contrat.", [])
            excerpts = [
                {
                    "source": chunk.source,
                    "excerpt": _PSEUDONYMOUS_ID.sub(
                        "[identifiant masqué]", chunk.content),
                }
                for chunk in chunks
            ]
            return ToolOutput(
                json.dumps(excerpts, ensure_ascii=False), chunks)

        if name == "search_my_claims":
            if not self.assure_id and not self.prestataire_id:
                raise ValueError(
                    "search_my_claims requires an authenticated user context")
            self._require_arguments(
                arguments, {"date_from", "date_to", "invoice_id"})
            date_from = self._parse_date(arguments["date_from"], "date_from")
            date_to = self._parse_date(arguments["date_to"], "date_to")
            if date_from and date_to and date_from > date_to:
                raise ValueError("date_from must not be after date_to")
            invoice_id = arguments["invoice_id"]
            if invoice_id is not None and (
                    not isinstance(invoice_id, str)
                    or not _INVOICE_ID.fullmatch(invoice_id)):
                raise ValueError("invoice_id must use FAC- followed by 8 digits")

            with self.engine.connect() as connection:
                if self.prestataire_id:
                    query = _PROVIDER_CLAIMS_SQL
                    params = {
                        "prestataire_id": self.prestataire_id,
                        "date_from": date_from,
                        "date_to": date_to,
                        "invoice_id": (
                            invoice_id.upper() if invoice_id else None),
                    }
                else:
                    query = _CLAIMS_SQL
                    params = {
                        "assure_id": self.assure_id,
                        "contract_id": self.contract_id,
                        "date_from": date_from,
                        "date_to": date_to,
                        "invoice_id": (
                            invoice_id.upper() if invoice_id else None),
                    }
                rows = connection.execute(query, params).mappings().all()
            if not rows:
                return ToolOutput(
                    "Aucune facture correspondante trouvée pour l'assuré "
                    "connecté.", [], claims=[])
            claims = [
                {
                    "facture_id": row["facture_id"],
                    "date_reception": self._format_date(row["date_reception"]),
                    "date_soin": self._format_date(row["date_soin"]),
                    "date_traitement": self._format_date(
                        row["date_traitement"]),
                    "type_facture": row["type_facture"],
                    "montant_total": row["montant_total"],
                    "montant_pris_en_charge": row["montant_pris_en_charge"],
                    "statut": self._display_status(row["statut"]),
                }
                for row in rows
            ]
            return ToolOutput(
                json.dumps(
                    claims, ensure_ascii=False, default=self._json_default),
                [], claims=claims)

        if name == "get_my_reimbursement_total":
            self._require_arguments(arguments, set())
            if not self.assure_id:
                raise ValueError(
                    "get_my_reimbursement_total requires an assured context")
            with self.engine.connect() as connection:
                row = connection.execute(_REIMBURSEMENT_TOTAL_SQL, {
                    "assure_id": self.assure_id,
                    "contract_id": self.contract_id,
                }).mappings().one()
            aggregate = {
                "total_rembourse": row["total_rembourse"],
                "nombre_factures_payees": row["nombre_factures_payees"],
            }
            return ToolOutput(
                json.dumps(
                    aggregate, ensure_ascii=False,
                    default=self._json_default),
                [], aggregate=aggregate)

        raise ValueError(f"Unsupported agent tool: {name}")

    @staticmethod
    def _require_arguments(
        arguments: dict[str, Any], expected: set[str]
    ) -> None:
        if not isinstance(arguments, dict) or set(arguments) != expected:
            raise ValueError("Tool arguments do not match the allowed schema")

    @staticmethod
    def _parse_date(value: Any, name: str) -> date | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"{name} must be an ISO date or null")
        try:
            parsed = date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"{name} must use YYYY-MM-DD format") from error
        if parsed.isoformat() != value:
            raise ValueError(f"{name} must use YYYY-MM-DD format")
        return parsed

    @staticmethod
    def _format_date(value: date | None) -> str | None:
        return value.isoformat() if value else None

    @staticmethod
    def _display_date(value: str) -> str:
        return date.fromisoformat(value).strftime("%d/%m/%Y")

    @staticmethod
    def _format_amount(value: int | None) -> str:
        if value is None:
            return "non renseigné"
        return f"{value:,}".replace(",", " ") + " Ar"

    @staticmethod
    def _json_default(value: Any) -> Any:
        if isinstance(value, Decimal):
            return int(value) if value == value.to_integral_value() else float(value)
        raise TypeError(
            f"Object of type {type(value).__name__} is not JSON serializable")

    @staticmethod
    def _display_status(value: str) -> str:
        try:
            return _CLAIM_STATUS_LABELS[value]
        except KeyError:
            return "À confirmer auprès d'un gestionnaire"
