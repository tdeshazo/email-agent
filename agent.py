from __future__ import annotations

import json
import os
from datetime import timedelta
from typing import Any

import requests

from discord import Embed, make_notifier, send_webhook_chunked
from mail import GmailMessage, GmailQueryBuilder, GmailReader

DEFAULT_MAX_RESULTS = 50

TOOL_SCHEMA = [{
    "type": "function",
    "function": {
        "name": "notify",
        "description": "Notify the user of a relevant email",
        "parameters": {
            "type": "object",
            "required": ["summary"],
            "properties": {
                "summary": {"type": "string", "description": "A summary of the email"},
            },
        },
    },
}]


class EmailAgent:
    def __init__(
        self,
        ollama_chat_url: str | None = None,
        ollama_model: str | None = None,
        webhook_url: str | None = None,
        max_results: int = DEFAULT_MAX_RESULTS,
    ):
        self.ollama_chat_url = ollama_chat_url or os.getenv("OLLAMA_CHAT_URL")
        self.ollama_model = ollama_model or os.getenv("OLLAMA_MODEL")
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        self.max_results = max_results

    def ollama_chat(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.ollama_chat_url:
            raise ValueError("OLLAMA_CHAT_URL is required.")
        if not self.ollama_model:
            raise ValueError("OLLAMA_MODEL is required.")

        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "tools": TOOL_SCHEMA,
            "stream": False,
        }
        response = requests.post(self.ollama_chat_url, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def build_prompt(email: GmailMessage) -> str:
        body_preview = email.body().strip().replace("\n", " ")
        body_preview = body_preview[:500]
        return (
            "Decide if this email is important and if the user should be notified.\n"
            f"From: {email.sender()}\n"
            f"Subject: {email.subject()}\n"
            f"Snippet: {email.snippet()}\n"
            f"Body preview: {body_preview}\n"
            "If important, call the `notify` tool with a concise `summary`."
        )

    @staticmethod
    def parse_tool_args(raw_args: Any) -> dict[str, Any]:
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    def check_email(self, email: GmailMessage) -> list[Embed]:
        message_id = email.id()
        if not message_id:
            print("Skipping email with no message id.")
            return []

        messages: list[dict[str, Any]] = [{"role": "user", "content": self.build_prompt(email)}]
        notify = make_notifier(message_id, email.subject())
        embeds: list[Embed] = []

        # 1) Model proposes a tool call.
        resp1 = self.ollama_chat(messages)
        assistant_msg = resp1.get("message", {})
        messages.append(assistant_msg)

        # 2) Run tool(s) and append tool result(s).
        tool_calls = assistant_msg.get("tool_calls") or []
        for tc in tool_calls:
            function = tc.get("function", {})
            fn = function.get("name")
            args = self.parse_tool_args(function.get("arguments"))
            if fn == "notify":
                summary = str(args.get("summary", "")).strip()
                if not summary:
                    continue
                embeds.append(notify(summary=summary))
                messages.append(
                    {
                        "role": "tool",
                        "tool_name": fn,
                        "content": "Notification queued.",
                    }
                )

        # 3) Model produces final answer.
        resp2 = self.ollama_chat(messages)
        print(resp2.get("message", {}).get("content", ""))
        return embeds

    def get_recent_messages(self, time_delta: timedelta | None) -> list[GmailMessage]:
        reader = GmailReader()
        query = (
            GmailQueryBuilder()
            .newer_than("1d")
            .in_("inbox")
        )
        return reader.get_messages(
            query,
            max_results=self.max_results,
            time_delta=time_delta,
        )

    def run(self, time_delta: timedelta | None) -> None:
        messages = self.get_recent_messages(time_delta=time_delta)
        embeds: list[Embed] = []

        for entry in messages:
            try:
                embeds.extend(self.check_email(entry))
            except Exception as exc:
                print(f"Failed to process message {entry.id()}: {exc}")

        if not embeds:
            print("No notifications were queued.")
            return

        try:
            responses = send_webhook_chunked(embeds=embeds, url=self.webhook_url)
            status_codes = ", ".join(str(item.status_code) for item in responses)
            print(
                f"Queued notifications sent ({len(embeds)} embeds across "
                f"{len(responses)} webhook message(s); status: {status_codes})."
            )
        except Exception as exc:
            print(f"Failed to send queued notifications: {exc}")
