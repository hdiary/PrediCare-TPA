"""Real PostgreSQL proof that the invoice write set rolls back as one unit."""
import os

import psycopg
from psycopg.rows import dict_row

from api import repositories as repo


def main():
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        source = conn.execute(
            "SELECT f.*, l.code, l.type_ligne, l.libelle, l.quantite, l.prix_unitaire, l.montant "
            "FROM factures f JOIN lignes_facture l USING (facture_id) LIMIT 1"
        ).fetchone()
        invoice_id = "FAC-99999998"
        conn.execute("DELETE FROM factures WHERE facture_id = %s", (invoice_id,))
        clean = {
            "facture_id": invoice_id, "numero_facture": "ROLLBACK-TEST",
            "prestataire_id": source["prestataire_id"], "assure_id": source["assure_id"],
            "contrat_id": source["contrat_id"], "ordonnance_id": source["ordonnance_id"],
            "type_facture": source["type_facture"], "date_soin": source["date_soin"].isoformat(),
            "heure_soin": source["heure_soin"].strftime("%H:%M"), "date_facture": source["date_facture"].isoformat(),
            "devise": source["devise"], "montant_total": source["montant_total"],
            "lignes": [{"num_ligne": 1, **{k: source[k] for k in ("code", "type_ligne", "libelle", "quantite", "prix_unitaire", "montant")}}],
        }
        try:
            with conn.transaction():
                repo.insert_facture(conn, clean, source["date_reception"], None)
                raise RuntimeError("injected failure after invoice and lines")
        except RuntimeError:
            pass
        assert conn.execute("SELECT 1 FROM factures WHERE facture_id = %s", (invoice_id,)).fetchone() is None
        print({"rollback": "OK", "facture_id": invoice_id})


if __name__ == "__main__":
    main()
