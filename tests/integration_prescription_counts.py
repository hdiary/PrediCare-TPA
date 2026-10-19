"""Measure phase 5c checks on every prescription in the Docker PostgreSQL."""
from collections import Counter
import os

import psycopg
from psycopg.rows import dict_row

from api.services.prescription_anomalies import RULES


class ConfigConn:
    def execute(self, sql, params=()):
        class Result:
            def fetchone(self):
                return {"valeur": "10"}
        return Result()


def main():
    counts = Counter()
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        ordonnances = {r["ordonnance_id"]: r for r in conn.execute("SELECT * FROM ordonnances")}
        lines = {}
        for row in conn.execute("SELECT * FROM ordonnance_lignes"):
            lines.setdefault(row["ordonnance_id"], []).append(row)
        prescribers = {r["prestataire_id"]: r for r in conn.execute("SELECT * FROM prestataires")}
        assures = {r["assure_id"]: r for r in conn.execute("SELECT * FROM assures")}
        codes = [r["code"] for rows in lines.values() for r in rows]
        actes = {r["code_acte"]: r for r in conn.execute(
            "SELECT * FROM referentiel_actes WHERE code_acte = ANY(%s)", (list(set(codes)),)
        )}
        fake = ConfigConn()
        for ordonnance_id, ordonnance in ordonnances.items():
            context = {
                "prescripteur": prescribers.get(ordonnance["prescripteur_id"]),
                "assure": assures.get(ordonnance["assure_id"]),
                "actes": actes,
            }
            findings = (rule(fake, ordonnance, lines.get(ordonnance_id, []), context)
                        for rule in RULES)
            counts.update(f.code for f in findings if f)
    print({"ordonnances": len(ordonnances), "effectifs": dict(sorted(counts.items()))})


if __name__ == "__main__":
    main()
