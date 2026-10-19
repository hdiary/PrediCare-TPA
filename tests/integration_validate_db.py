"""Run the real invoice validator over the PostgreSQL dataset in batches."""
import os
from collections import Counter, defaultdict

import psycopg
from psycopg.rows import dict_row

from api.validation import validate_invoice


class BatchConn:
    def __init__(self, ids, providers, categories, refs, ordonnances):
        self.ids = ids
        self.providers = providers
        self.categories = categories
        self.refs = refs
        self.ordonnances = ordonnances

    def execute(self, query, params=()):
        q = " ".join(query.split()).upper()
        if "FROM ASSURES" in q:
            return Cursor({"x": 1} if params[0] in self.ids else None)
        if "FROM PRESTATAIRES WHERE" in q:
            return Cursor({"x": 1} if params[0] in self.providers else None)
        if "FROM GARANTIES" in q:
            return Cursor({"x": 1} if params[0] in self.categories else None)
        if "FROM ORDONNANCES" in q:
            return Cursor(self.ordonnances.get(params[0]))
        if "FROM REFERENTIEL_ACTES" in q or "FROM REFERENTIEL_MEDICAMENTS" in q:
            codes = params[0]
            return Cursor(rows=[self.refs[c] for c in codes if c in self.refs])
        raise AssertionError(f"unexpected validator query: {query}")


class Cursor:
    def __init__(self, row=None, rows=None):
        self.row, self.rows = row, rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


def main():
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        ids = {r["assure_id"] for r in conn.execute("SELECT assure_id FROM assures")}
        providers = {r["prestataire_id"] for r in conn.execute("SELECT prestataire_id FROM prestataires")}
        categories = {r["categorie"] for r in conn.execute("SELECT DISTINCT categorie FROM garanties")}
        ordonnances = {r["ordonnance_id"]: r for r in conn.execute("SELECT ordonnance_id, type_ordonnance FROM ordonnances")}
        refs = {}
        refs.update({r["code"]: r for r in conn.execute("SELECT code_acte AS code, 'ACTE' AS type_ligne, libelle FROM referentiel_actes")})
        refs.update({r["code"]: r for r in conn.execute("SELECT code_medicament AS code, 'MEDICAMENT' AS type_ligne, libelle FROM referentiel_medicaments")})
        batch_conn = BatchConn(ids, providers, categories, refs, ordonnances)
        line_rows = conn.execute("SELECT facture_id, num_ligne, code, type_ligne, quantite, prix_unitaire, montant FROM lignes_facture ORDER BY facture_id, num_ligne")
        lines = defaultdict(list)
        for row in line_rows:
            lines[row["facture_id"]].append(dict(row))
        rejected = Counter()
        total = 0
        for row in conn.execute("SELECT * FROM factures ORDER BY facture_id"):
            payload = {key: row[key] for key in ("facture_id", "numero_facture", "prestataire_id", "assure_id", "contrat_id", "ordonnance_id", "type_facture", "date_soin", "heure_soin", "date_facture", "date_reception", "canal_reception", "mode_reglement", "attestation_pec_id", "entente_prealable_id", "devise", "montant_total")}
            payload["date_soin"] = payload["date_soin"].isoformat()
            payload["date_facture"] = payload["date_facture"].isoformat()
            payload["date_reception"] = payload["date_reception"].isoformat()
            payload["heure_soin"] = payload["heure_soin"].strftime("%H:%M")
            payload["lignes"] = [{key: line[key] for key in ("code", "type_ligne", "quantite", "prix_unitaire", "montant")} for line in lines[row["facture_id"]]]
            errors, _ = validate_invoice(payload, batch_conn)
            rejected.update(error["code"] for error in errors)
            total += 1
        print({"total": total, "rejets_par_code": dict(sorted(rejected))})


if __name__ == "__main__":
    main()
