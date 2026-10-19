import unittest

from rag.retriever import RetrievedChunk
from rag.structured_answers import (
    answer_from_contract,
    answer_from_guarantee_table,
    is_direct_contract_question,
    is_exclusion_question,
    is_guarantee_table_question,
)


def _chunk(content: str, article: str | None = "Article 5 – Tableau des garanties"):
    return RetrievedChunk(
        content=content,
        scope="formula",
        contract_id=None,
        formula="PREMIUM",
        article=article,
        page_start=1,
        page_end=1,
        filename="Conditions_Generales_PREMIUM.pdf",
        score=0.9,
    )


def _contract_chunk(content: str) -> RetrievedChunk:
    return RetrievedChunk(
        content=content,
        scope="contract",
        contract_id="CTR-000066",
        formula=None,
        article=None,
        page_start=1,
        page_end=1,
        filename="CP_CTR-000066.pdf",
        score=0.9,
    )


class StructuredAnswerTests(unittest.TestCase):
    def test_answers_general_guarantees_from_article_five(self):
        chunk = _chunk(
            "[Formule PREMIUM > Article 5] "
            "Plafond annuel global par bénéficiaire : 20 000 000 Ar. "
            "Dentaire 90 % 2 000 000 Ar Aucune 30 jours "
            "Optique 90 % 800 000 Ar Aucune 60 jours"
        )

        self.assertTrue(is_guarantee_table_question(
            "Quelles sont mes garanties principales ?"))
        result = answer_from_guarantee_table(
            "Quelles sont mes garanties principales ?", [chunk])

        self.assertIsNotNone(result)
        answer, source = result
        self.assertIn("20 000 000 Ar", answer)
        self.assertIn("Dentaire : 90 %", answer)
        self.assertIn("Optique : 90 %", answer)
        self.assertEqual(source, chunk)

    def test_extracts_dental_coverage_from_article_five(self):
        chunk = _chunk(
            "[Formule PREMIUM > Article 5] "
            "Dentaire 90 % 2 000 000 Ar Aucune 30 jours"
        )

        result = answer_from_guarantee_table(
            "Quel est le taux de remboursement en dentaire ?", [chunk])

        self.assertIsNotNone(result)
        answer, source = result
        self.assertIn("90 %", answer)
        self.assertIn("2 000 000 Ar", answer)
        self.assertIn("30 jours", answer)
        self.assertEqual(source, chunk)

    def test_does_not_extract_guarantee_from_other_article(self):
        chunk = _chunk(
            "Dentaire 90 % 2 000 000 Ar Aucune 30 jours",
            article="Article 1 – Objet du contrat",
        )

        self.assertIsNone(answer_from_guarantee_table(
            "Quel est le taux de remboursement en dentaire ?", [chunk]))

    def test_only_recognizes_category_coverage_questions_as_structured(self):
        self.assertTrue(is_guarantee_table_question(
            "Quel est le taux de remboursement en dentaire ?"))
        self.assertTrue(is_guarantee_table_question(
            "Quelles sont mes garanties principales ?"))

    def test_answers_beneficiary_question_without_pseudonymous_ids(self):
        chunk = _chunk(
            "Bénéficiaires (identifiants pseudonymisés) "
            "ASS-C60624BAFB ASSURE_PRINCIPAL M 1993 "
            "ASS-1EDC967FF9 CONJOINT F 1999 "
            "ASS-009B02505D ENFANT M 2019",
            article=None,
        )
        chunk = RetrievedChunk(
            content=chunk.content,
            scope="contract",
            contract_id="CTR-000048",
            formula=None,
            article=None,
            page_start=1,
            page_end=1,
            filename="CP_CTR-000048.pdf",
            score=0.5,
        )

        result = answer_from_contract(
            "Qui sont les bénéficiaires de mon contrat ?", [chunk])

        self.assertIsNotNone(result)
        answer, source = result
        self.assertIn("assuré principal", answer)
        self.assertIn("conjoint", answer)
        self.assertIn("enfant", answer)
        self.assertNotIn("ASS-", answer)
        self.assertEqual(source, chunk)

    def test_prefers_contract_specific_global_ceiling(self):
        chunk = _contract_chunk(
            "Plafond annuel global par bénéficiaire : 20 000 000 Ar.")

        result = answer_from_contract(
            "Quel est le plafond annuel global de mon contrat ?", [chunk])

        self.assertIsNotNone(result)
        answer, source = result
        self.assertIn("20 000 000 Ar", answer)
        self.assertEqual(source, chunk)

    def test_extracts_annual_premium_per_beneficiary_and_total(self):
        chunk = _contract_chunk(
            "Prime annuelle : 980 000 Ar par bénéficiaire, soit "
            "1 960 000 Ar pour 2 bénéficiaire(s)."
        )

        question = "Quelle est ma prime annuelle ?"
        result = answer_from_contract(question, [chunk])

        self.assertIsNotNone(result)
        answer, source = result
        self.assertIn("980 000 Ar par bénéficiaire", answer)
        self.assertIn("1 960 000 Ar pour 2 bénéficiaires", answer)
        self.assertEqual(source, chunk)
        self.assertTrue(is_direct_contract_question(question))

    def test_extracts_company_subscriber_without_business_description(self):
        chunk = _contract_chunk(
            "Souscripteur : Mahery Tourisme SAS (Hôtellerie & tourisme) "
            "Date d'effet de la police : 2021-03-26."
        )

        result = answer_from_contract(
            "Quel est le nom du souscripteur ?", [chunk])

        self.assertIsNotNone(result)
        answer, source = result
        self.assertIn("Mahery Tourisme SAS", answer)
        self.assertNotIn("Hôtellerie", answer)
        self.assertEqual(source, chunk)
        self.assertTrue(is_direct_contract_question(
            "Quel est le nom du souscripteur ?"))

    def test_identifies_individual_subscriber_without_personal_identity(self):
        chunk = _contract_chunk(
            "Souscripteur : Adhésion individuelle (Particulier) "
            "Date d'effet de la police : 2019-04-11."
        )

        result = answer_from_contract(
            "Quel est le nom du souscripteur ?", [chunk])

        self.assertIsNotNone(result)
        answer, source = result
        self.assertIn("adhésion individuelle", answer)
        self.assertEqual(source, chunk)

    def test_does_not_answer_other_subscriber_questions_with_its_name(self):
        self.assertFalse(is_direct_contract_question(
            "Quel est le numéro de téléphone du souscripteur ?"))

    def test_extracts_contract_status(self):
        chunk = _contract_chunk(
            "Date d'effet du contrat : 2025-11-28 – Fin : 2026-03-27 – "
            "Statut : RESILIE"
        )

        question = "Quel est le statut de mon contrat ?"
        result = answer_from_contract(question, [chunk])

        self.assertIsNotNone(result)
        answer, source = result
        self.assertIn("RESILIE", answer)
        self.assertEqual(source, chunk)
        self.assertTrue(is_direct_contract_question(question))

    def test_extracts_contract_end_date_in_iso_format(self):
        chunk = _contract_chunk("Fin : 2026-03-27 – Statut : RESILIE")

        question = "Quelle est la date de fin de mon contrat ?"
        result = answer_from_contract(question, [chunk])

        self.assertIsNotNone(result)
        answer, source = result
        self.assertIn("2026-03-27", answer)
        self.assertEqual(source, chunk)
        self.assertTrue(is_direct_contract_question(question))

    def test_extracts_policy_number_from_contract_conditions(self):
        chunk = _contract_chunk("[Contrat CTR-000066] Police POL-2022-2780.")

        result = answer_from_contract(
            "Quel est le numéro de police de mon contrat ?", [chunk])

        self.assertIsNotNone(result)
        answer, source = result
        self.assertIn("POL-2022-2780", answer)
        self.assertEqual(source, chunk)
        self.assertTrue(is_direct_contract_question(
            "Quel est le numéro de police de mon contrat ?"))

    def test_extracts_exclusions_from_article_ten(self):
        chunk = _chunk(
            "[Formule PREMIUM > Article 10 – Exclusions] "
            "\x7f Fortifiants, compléments alimentaires. "
            "\x7f Soins à visée esthétique. "
            "\x7f Soins pendant un délai de carence.",
            article="Article 10 – Exclusions",
        )

        self.assertTrue(is_exclusion_question(
            "Quelles sont les exclusions de ma formule ?"))
        result = answer_from_contract(
            "Quelles sont les exclusions de ma formule ?", [chunk])

        self.assertIsNotNone(result)
        answer, source = result
        self.assertIn("Fortifiants, compléments alimentaires.", answer)
        self.assertIn("Soins à visée esthétique.", answer)
        self.assertNotIn("coordonnées", answer)
        self.assertEqual(source, chunk)

    def test_maps_general_practitioner_question_to_consultation_row(self):
        chunk = _chunk(
            "[Formule PREMIUM > Article 5] "
            "Consultation 100 % 3 000 000 Ar Aucune Aucune"
        )

        result = answer_from_guarantee_table(
            "Ma consultation chez le généraliste est-elle couverte ?", [chunk])

        self.assertIsNotNone(result)
        answer, source = result
        self.assertIn("100 %", answer)
        self.assertIn("3 000 000 Ar", answer)
        self.assertEqual(source, chunk)

    def test_does_not_answer_dialysis_question_with_whole_table(self):
        chunk = _chunk(
            "[Formule PREMIUM > Article 5] "
            "Consultation 100 % 3 000 000 Ar Aucune Aucune"
        )

        result = answer_from_guarantee_table(
            "Quel est le plafond pour la dialyse ?", [chunk])

        self.assertIsNotNone(result)
        self.assertIn("ne précise pas de ligne", result[0])


if __name__ == "__main__":
    unittest.main()
