import unittest
from unittest.mock import MagicMock, patch

from rag.agent import RagAgent

class RagAgentToolTests(unittest.TestCase):
    def test_claim_questions_without_assured_context_are_not_sent_to_llm(self):
        embeddings = MagicMock()
        retriever = MagicMock()
        llm = MagicMock()
        cache = MagicMock()
        audit = MagicMock()
        agent = RagAgent(embeddings, retriever, llm, cache, audit)

        response = agent.answer(
            "Où en est mon dossier ?",
            contract_id="CTR-000615",
            user_pseudo_id="PROMPT-TEST",
            role="assure",
        )

        self.assertIn("--assure-id", response.answer)
        embeddings.embed.assert_not_called()
        llm.complete_with_tools.assert_not_called()
        audit.write.assert_called_once()

    def test_claim_status_uses_deterministic_tool_without_llm_or_cache(self):
        embeddings = MagicMock()
        retriever = MagicMock()
        llm = MagicMock()
        cache = MagicMock()
        audit = MagicMock()
        toolkit = MagicMock()
        toolkit.recent_claims_answer.return_value = (
            "FAC-00000001 : statut REJETEE")
        agent = RagAgent(embeddings, retriever, llm, cache, audit)

        with patch("rag.agent.AgentToolkit", return_value=toolkit):
            response = agent.answer(
                "Liste mes dernières factures avec leur date de réception et leur statut.",
                contract_id="CTR-000048",
                user_pseudo_id="PROMPT-TEST",
                role="assure",
                assure_id="ASS-C60624BAFB",
            )

        self.assertIn("statut REJETEE", response.answer)
        self.assertIn("historique des factures", response.answer)
        self.assertFalse(response.sources)
        toolkit.recent_claims_answer.assert_called_once()
        llm.complete_with_tools.assert_not_called()
        embeddings.embed.assert_not_called()
        cache.get.assert_not_called()
        cache.put.assert_not_called()
        audit.write.assert_called_once()
        self.assertEqual(
            audit.write.call_args.kwargs["tools_used"],
            ["search_my_claims"],
        )
        self.assertEqual(audit.write.call_args.kwargs["tokens_in"], 0)
        self.assertEqual(audit.write.call_args.kwargs["tokens_out"], 0)

    def test_provider_claim_status_uses_provider_scoped_tool(self):
        embeddings = MagicMock()
        retriever = MagicMock()
        llm = MagicMock()
        cache = MagicMock()
        audit = MagicMock()
        toolkit = MagicMock()
        toolkit.recent_claims_answer.return_value = "FAC-00000001 : Payée"
        agent = RagAgent(embeddings, retriever, llm, cache, audit)

        with patch("rag.agent.AgentToolkit", return_value=toolkit) as toolkit_class:
            toolkit_class.is_claim_question.return_value = True
            toolkit_class.is_reimbursement_total_question.return_value = False
            toolkit_class.is_claim_status_question.return_value = True
            response = agent.answer(
                "Où en est ma facture ?",
                contract_id=None,
                user_pseudo_id="PRE-00123",
                role="professionnel_sante",
                prestataire_id="PRE-00123",
            )

        self.assertIn("FAC-00000001", response.answer)
        self.assertEqual(
            toolkit_class.call_args.kwargs["prestataire_id"], "PRE-00123")
        toolkit.recent_claims_answer.assert_called_once()
        llm.complete_with_tools.assert_not_called()
        embeddings.embed.assert_not_called()
        cache.get.assert_not_called()
        cache.put.assert_not_called()


if __name__ == "__main__":
    unittest.main()
