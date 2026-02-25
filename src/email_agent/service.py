from __future__ import annotations

import json
import os
from datetime import timedelta
from typing import Any
from collections.abc import Callable

from .clients.discord_client import Embed, make_notifier, send_webhook_chunked
from .clients.gmail_client import GmailMessage, GmailQueryBuilder, GmailReader
from .clients.ollama_client import OllamaClient
from .models import DEFAULT_MAX_RESULTS

DEFAULT_SYSTEM_PROMPT = (
    "You triage email for career opportunities. "
    "Call `notify` only for recruiter/hiring outreach, interview scheduling, application status updates, "
    "recruiter feedback/next steps, or clearly relevant job opportunities "
    "(software/backend/data/automation/LIMS/Python/Go/SQL). "
    "Ignore newsletters, promos, generic digests, social alerts, receipts, and unrelated email. "
    "If unsure but likely recruiting/hiring, notify. "
    "Call `notify` at most once. "
    "Summary must be one sentence with: type, company/sender, role (if any), action/deadline (if any)."
)


class EmailAgent:
    def __init__(
        self,
        ollama_client: OllamaClient | None = None,
        gmail_reader_factory: Callable[[], GmailReader] = GmailReader,
        webhook_url: str | None = None,
        max_results: int = DEFAULT_MAX_RESULTS,
        system_prompt: str | None = None,
    ):
        self.ollama_client = ollama_client or OllamaClient()
        self.gmail_reader_factory = gmail_reader_factory
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        self.max_results = max_results
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    def ollama_chat(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        return self.ollama_client.chat(messages)

    @staticmethod
    def build_prompt(email: GmailMessage) -> str:
        body_preview = email.body().strip().replace("\n", " ")
        body_preview = body_preview[:700]
        return (
            f"From: {email.sender()}\n"
            f"Subject: {email.subject()}\n"
            f"Snippet: {email.snippet()}\n"
            f"Body: {body_preview}\n"
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

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.build_prompt(email)},
        ]
        notify = make_notifier(message_id, email.subject())
        embeds: list[Embed] = []

        resp1 = self.ollama_chat(messages)
        assistant_msg = resp1.get("message", {})
        messages.append(assistant_msg)

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

        resp2 = self.ollama_chat(messages)
        print(resp2.get("message", {}).get("content", ""))
        return embeds

    def get_recent_messages(self, time_delta: timedelta | None) -> list[GmailMessage]:
        reader = self.gmail_reader_factory()
        query = GmailQueryBuilder().newer_than("1d").in_("inbox")
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
