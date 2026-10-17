import unittest
from unittest.mock import patch

import httpx

from rag.llm import ChatCompletionClient


class ChatCompletionClientTests(unittest.TestCase):
    def test_uses_configured_timeout(self):
        response = httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Réponse"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
            request=httpx.Request(
                "POST", "http://ollama/v1/chat/completions"),
        )
        with patch("rag.llm.httpx.post", return_value=response) as post:
            client = ChatCompletionClient(
                "ollama", "qwen3:4b",
                "http://ollama/v1/chat/completions", timeout=300)
            result = client.complete("system", "question")

        self.assertEqual(result, ("Réponse", 3, 2))
        self.assertEqual(post.call_args.kwargs["timeout"], 300)


if __name__ == "__main__":
    unittest.main()
