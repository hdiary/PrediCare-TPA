"""OpenAI-compatible embedding client."""
import math
from urllib.parse import urlparse

import httpx


class EmbeddingClient:
    def __init__(self, api_key: str, model: str, dimensions: int,
                 api_url: str, timeout: float = 120.0):
        if not model:
            raise ValueError("EMBEDDING_MODEL is required")
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.api_url = api_url
        self.timeout = timeout
        self.ollama_native_api = (
            urlparse(api_url).path.rstrip("/").endswith("/api/embed"))
        if not self.ollama_native_api and not api_key:
            raise ValueError(
                "LLM_API_KEY is required for OpenAI-compatible embeddings")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        headers = {}
        if self.api_key and not self.ollama_native_api:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.ollama_native_api:
            payload = {"model": self.model, "input": texts}
        else:
            payload = {
                "model": self.model,
                "input": texts,
                "dimensions": self.dimensions,
            }
        response = httpx.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if self.ollama_native_api:
            vectors = payload.get("embeddings")
        else:
            data = payload.get("data")
            if data is None:
                keys = ", ".join(sorted(payload)) if isinstance(
                    payload, dict) else type(payload).__name__
                raise ValueError(
                    "Embedding API response is missing 'data'; "
                    f"received keys/type: {keys}. Check EMBEDDING_API_URL "
                    "(expected an OpenAI /v1/embeddings endpoint or Ollama "
                    "/api/embed).")
            vectors = [item["embedding"] for item in
                       sorted(data, key=lambda item: item["index"])]
        if not isinstance(vectors, list):
            raise ValueError(
                "Embedding API response is missing its vector list "
                f"({'embeddings' if self.ollama_native_api else 'data'}).")
        if len(vectors) != len(texts):
            raise ValueError("Embedding service returned an unexpected vector count")
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self.dimensions}, "
                    f"received {len(vector)}")
            if not all(math.isfinite(float(value)) for value in vector):
                raise ValueError("Embedding service returned a non-finite value")
        return [[float(value) for value in vector] for vector in vectors]
