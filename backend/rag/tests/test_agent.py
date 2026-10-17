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


if __name__ == "__main__":
    unittest.main()
