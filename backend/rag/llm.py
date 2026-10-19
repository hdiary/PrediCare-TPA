"""OpenAI-compatible chat-completion client."""
from typing import Any

import httpx


class ChatCompletionClient:
    def __init__(self, api_key: str, model: str, api_url: str,
                 timeout: float = 300.0):
        if not api_key or not model:
            raise ValueError("LLM_API_KEY and LLM_MODEL are required")
        self.api_key = api_key
        self.model = model
        self.api_url = api_url
        self.timeout = timeout

    def complete(self, system_prompt: str, user_prompt: str) -> tuple[str, int, int]:
        response = httpx.post(
            self.api_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        answer = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage", {})
        return answer, int(usage.get("prompt_tokens", 0)), int(
            usage.get("completion_tokens", 0))

    def complete_with_tools(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], int, int]:
        response = httpx.post(
            self.api_url,
            headers={"Authorization": f"******"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    *messages,
                ],
                "tools": tools,
                "tool_choice": "auto",
                "temperature": 0,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload["choices"][0]["message"]
        usage = payload.get("usage", {})
        if not isinstance(message, dict):
            raise ValueError("LLM returned an invalid assistant message")
        return (
            message,
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
        )
