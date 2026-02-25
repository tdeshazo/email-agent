from __future__ import annotations

import os
from typing import Any

import requests
from requests.exceptions import ReadTimeout

TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "notify",
            "description": "Notify the user of a relevant email",
            "parameters": {
                "type": "object",
                "required": ["summary"],
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "A summary of the email",
                    },
                },
            },
        },
    }
]


class OllamaClient:
    def __init__(
        self,
        chat_url: str | None = None,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ):
        self.chat_url = chat_url or os.getenv("OLLAMA_CHAT_URL")
        self.model = model or os.getenv("OLLAMA_MODEL")
        self.tools = tools or TOOL_SCHEMA

    def chat(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.chat_url:
            raise ValueError("OLLAMA_CHAT_URL is required.")
        if not self.model:
            raise ValueError("OLLAMA_MODEL is required.")

        payload = {
            "model": self.model,
            "messages": messages,
            "tools": self.tools,
            "stream": False,
            "keep_alive": "30m",
            "think": False,
            "options": {
                "num_ctx": 4096,
                "temperature": 0.1,
            },
        }

        last_exc = None
        for attempt in range(2):
            try:
                response = requests.post(
                    self.chat_url,
                    json=payload,
                    timeout=(5, 180),
                )
                response.raise_for_status()
                return response.json()
            except ReadTimeout as exc:
                last_exc = exc
                if attempt == 0:
                    continue
                raise
        raise last_exc
