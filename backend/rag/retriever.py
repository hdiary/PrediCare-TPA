"""Contract-filtered pgvector retrieval."""
from dataclasses import dataclass
import json

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class RetrievedChunk:
    content: str
    scope: str
    contract_id: str | None
    formula: str | None
    article: str | None
    page_start: int | None
    page_end: int | None
    filename: str
    score: float

    @property
    def source(self) -> str:
        page = str(self.page_start) if self.page_start else "?"
        article = self.article or "Sans article"
        if self.scope == "contract":
            subject = f"Contrat {self.contract_id}"
        elif self.scope == "formula":
            subject = f"Formule {self.formula}"
        else:
            subject = "Document général"
        return f"{subject} ({self.filename}), {article}, page {page}"


def _vector_literal(values: list[float]) -> str:
    return json.dumps(values, separators=(",", ":"))


class ContractRetriever:
    def __init__(self, engine: Engine, top_k: int, min_score: float):
        self.engine = engine
        self.top_k = top_k
        self.min_score = min_score

    def search(self, query_embedding: list[float],
               contract_id: str,
               include_guarantee_table: bool = False,
               include_exclusions: bool = False,
               ) -> list[RetrievedChunk]:
        query = text("""
            WITH target AS (
                SELECT formule FROM v_rag_contrat_formules
                WHERE contrat_id = :contract_id
            ),
            scored AS (
                SELECT c.content, c.scope, c.contrat_id AS contract_id,
                       c.formule AS formula, c.article, c.page_start,
                       c.page_end, d.filename,
                       1 - (c.embedding <=> CAST(:embedding AS vector)) AS score,
                       c.embedding <=> CAST(:embedding AS vector) AS distance
                FROM rag_chunks AS c
                JOIN rag_documents AS d ON d.id = c.document_id
                CROSS JOIN target
                WHERE (c.scope = 'contract' AND c.contrat_id = :contract_id)
                   OR (c.scope = 'global')
                   OR (c.scope = 'formula' AND c.formule = target.formule)
            ),
            contract_context AS (
                SELECT * FROM scored
                WHERE scope = 'contract' AND contract_id = :contract_id
                ORDER BY distance
                LIMIT 1
            ),
            guarantee_context AS (
                SELECT * FROM scored
                WHERE :include_guarantee_table
                  AND scope = 'formula'
                  AND article ILIKE 'Article 5%'
                ORDER BY distance
                LIMIT 1
            ),
            exclusion_context AS (
                SELECT * FROM scored
                WHERE :include_exclusions
                  AND scope = 'formula'
                  AND article ILIKE 'Article 10%'
                ORDER BY distance
                LIMIT 1
            ),
            other_context AS (
                SELECT * FROM scored
                WHERE scope != 'contract'
                  AND (
                    (
                      NOT :include_guarantee_table
                      OR scope != 'formula'
                      OR article NOT ILIKE 'Article 5%'
                    )
                    AND (
                      NOT :include_exclusions
                      OR scope != 'formula'
                      OR article NOT ILIKE 'Article 10%'
                    )
                  )
                ORDER BY distance
                LIMIT GREATEST(
                    :top_k - 1
                    - CASE WHEN :include_guarantee_table
                      AND EXISTS (SELECT 1 FROM guarantee_context)
                      THEN 1 ELSE 0 END
                    - CASE WHEN :include_exclusions
                      AND EXISTS (SELECT 1 FROM exclusion_context)
                      THEN 1 ELSE 0 END,
                    0
                )
            )
            SELECT content, scope, contract_id, formula, article, page_start,
                   page_end, filename, score
            FROM (
                SELECT * FROM contract_context
                UNION ALL
                SELECT * FROM guarantee_context
                UNION ALL
                SELECT * FROM exclusion_context
                UNION ALL
                SELECT * FROM other_context
            ) AS context
            ORDER BY score DESC
            LIMIT :top_k
        """)
        with self.engine.connect() as connection:
            rows = connection.execute(query, {
                "embedding": _vector_literal(query_embedding),
                "contract_id": contract_id,
                "top_k": self.top_k,
                "include_guarantee_table": include_guarantee_table,
                "include_exclusions": include_exclusions,
            }).mappings().all()
        return [
            RetrievedChunk(
                content=row["content"], scope=row["scope"],
                contract_id=row["contract_id"], formula=row["formula"],
                article=row["article"],
                page_start=row["page_start"], page_end=row["page_end"],
                filename=row["filename"], score=float(row["score"]),
            )
            for row in rows
            if row["scope"] == "contract"
            or (
                include_guarantee_table
                and row["scope"] == "formula"
                and row["article"]
                and row["article"].casefold().startswith("article 5")
            )
            or (
                include_exclusions
                and row["scope"] == "formula"
                and row["article"]
                and row["article"].casefold().startswith("article 10")
            )
            or float(row["score"]) >= self.min_score
        ]
