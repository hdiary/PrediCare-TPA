import unittest
from unittest.mock import patch

import httpx

from rag.embeddings import EmbeddingClient


class EmbeddingClientTests(unittest.TestCase):
    def test_parses_native_ollama_embed_response(self):
        vector = [0.25, 0.5, 0.75]
        response = httpx.Response(
            200, json={"model": "test-model", "embeddings": [vector]},
            request=httpx.Request("POST", "http://ollama/api/embed"))
        with patch("rag.embeddings.httpx.post", return_value=response) as post:
            client = EmbeddingClient(
                "", "test-model", 3, "http://ollama/api/embed")
            self.assertEqual(client.embed(["hello"]), [vector])

        self.assertEqual(post.call_args.kwargs["json"], {
            "model": "test-model", "input": ["hello"]})
        self.assertEqual(post.call_args.kwargs["headers"], {})

    def test_omits_api_key_for_native_ollama_even_if_configured(self):
        vector = [0.25, 0.5, 0.75]
        response = httpx.Response(
            200, json={"embeddings": [vector]},
            request=httpx.Request("POST", "http://ollama/api/embed"))
        with patch("rag.embeddings.httpx.post", return_value=response) as post:
            client = EmbeddingClient(
                "ollama", "test-model", 3, "http://ollama/api/embed")
            client.embed(["hello"])

        self.assertEqual(post.call_args.kwargs["headers"], {})

    def test_parses_openai_compatible_response(self):
        vector = [0.25, 0.5, 0.75]
        response = httpx.Response(
            200, json={"data": [{"index": 0, "embedding": vector}]},
            request=httpx.Request("POST", "https://example.test/v1/embeddings"))
        with patch("rag.embeddings.httpx.post", return_value=response):
            client = EmbeddingClient(
                "test-key", "test-model", 3,
                "https://example.test/v1/embeddings")
            self.assertEqual(client.embed(["hello"]), [vector])

    def test_reports_wrong_endpoint_shape(self):
        response = httpx.Response(
            200, json={"object": "list"},
            request=httpx.Request("POST", "http://ollama/v1"))
        with patch("rag.embeddings.httpx.post", return_value=response):
            client = EmbeddingClient(
                "ollama", "test-model", 3, "http://ollama/v1")
            with self.assertRaisesRegex(
                    ValueError, "Check EMBEDDING_API_URL"):
                client.embed(["hello"])

    def test_rejects_dimension_mismatch(self):
        response = httpx.Response(
            200,
            json={"embeddings": [[0.1, 0.2]]},
            request=httpx.Request("POST", "http://ollama/api/embed"))
        with patch("rag.embeddings.httpx.post", return_value=response):
            client = EmbeddingClient(
                "", "test-model", 3, "http://ollama/api/embed")
            with self.assertRaisesRegex(
                    ValueError, "expected 3, received 2"):
                client.embed(["hello"])


if __name__ == "__main__":
    unittest.main()
