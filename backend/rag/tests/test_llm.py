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

    def test_supports_openai_compatible_tool_calls(self):
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "search_my_claims",
                    "arguments": '{"date_from":null,"date_to":null,'
                                 '"invoice_id":null}',
                },
            }],
        }
        response = httpx.Response(
            200,
            json={
                "choices": [{"message": message}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            },
            request=httpx.Request(
                "POST", "http://ollama/v1/chat/completions"),
        )
        tools = [{"type": "function", "function": {"name": "search_my_claims"}}]
        messages = [{"role": "user", "content": "Où en est mon dossier ?"}]
        with patch("rag.llm.httpx.post", return_value=response) as post:
            client = ChatCompletionClient(
                "ollama", "qwen3:4b",
                "http://ollama/v1/chat/completions", timeout=300)
            result = client.complete_with_tools("system", messages, tools)

        self.assertEqual(result, (message, 5, 2))
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["tools"], tools)
        self.assertEqual(payload["tool_choice"], "auto")
        self.assertEqual(payload["messages"][-1], messages[0])


if __name__ == "__main__":
    unittest.main()
