from __future__ import annotations

import base64
import os.path
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Union

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailQueryBuilder:
    """Chainable builder for Gmail search queries."""

    def __init__(self):
        self._tokens: list[str] = []

    @staticmethod
    def _quote(value: str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("Query values cannot be empty.")
        if any(ch.isspace() for ch in text) or '"' in text:
            escaped = text.replace('"', '\\"')
            return f'"{escaped}"'
        return text

    @staticmethod
    def _date_value(value: Union[str, date]) -> str:
        if isinstance(value, date):
            return value.strftime("%Y/%m/%d")
        return str(value).strip().replace("-", "/")

    def _add(self, token: str):
        self._tokens.append(token)
        return self

    def text(self, value: str):
        return self._add(self._quote(value))

    def phrase(self, value: str):
        escaped = str(value).strip().replace('"', '\\"')
        return self._add(f'"{escaped}"')

    def from_(self, sender: str):
        return self._add(f"from:{self._quote(sender)}")

    def to(self, recipient: str):
        return self._add(f"to:{self._quote(recipient)}")

    def cc(self, recipient: str):
        return self._add(f"cc:{self._quote(recipient)}")

    def bcc(self, recipient: str):
        return self._add(f"bcc:{self._quote(recipient)}")

    def subject(self, value: str):
        return self._add(f"subject:{self._quote(value)}")

    def label(self, value: str):
        return self._add(f"label:{self._quote(value)}")

    def in_(self, value: str):
        return self._add(f"in:{self._quote(value)}")

    def has(self, value: str):
        return self._add(f"has:{self._quote(value)}")

    def filename(self, value: str):
        return self._add(f"filename:{self._quote(value)}")

    def is_(self, value: str):
        return self._add(f"is:{self._quote(value)}")

    def category(self, value: str):
        return self._add(f"category:{self._quote(value)}")

    def before(self, value: Union[str, date]):
        return self._add(f"before:{self._date_value(value)}")

    def after(self, value: Union[str, date]):
        return self._add(f"after:{self._date_value(value)}")

    def older_than(self, value: str):
        return self._add(f"older_than:{self._quote(value)}")

    def newer_than(self, value: str):
        return self._add(f"newer_than:{self._quote(value)}")

    def older(self, value: str):
        return self._add(f"older:{self._quote(value)}")

    def newer(self, value: str):
        return self._add(f"newer:{self._quote(value)}")

    def larger(self, value: str):
        return self._add(f"larger:{self._quote(value)}")

    def smaller(self, value: str):
        return self._add(f"smaller:{self._quote(value)}")

    def deliveredto(self, value: str):
        return self._add(f"deliveredto:{self._quote(value)}")

    def list_(self, value: str):
        return self._add(f"list:{self._quote(value)}")

    def include(self, raw_expression: str):
        return self._add(str(raw_expression).strip())

    def exclude(self, raw_expression: str):
        expr = str(raw_expression).strip()
        if not expr:
            raise ValueError("Query values cannot be empty.")
        return self._add(expr if expr.startswith("-") else f"-{expr}")

    def any_of(self, *expressions: str):
        values = [str(x).strip() for x in expressions if str(x).strip()]
        if not values:
            raise ValueError("any_of requires at least one expression.")
        return self._add(f"({' OR '.join(values)})")

    def build(self) -> str:
        return " ".join(self._tokens).strip()

    def __str__(self) -> str:
        return self.build()


class GmailMessage:
    """Wrapper around a Gmail API message resource."""

    def __init__(self, data: dict[str, Any]):
        self._data = data or {}
        self._text_parts_cache: dict[str, str] | None = None

    @property
    def raw(self) -> dict[str, Any]:
        return self._data

    def id(self) -> str | None:
        return self._data.get("id")

    def thread_id(self) -> str | None:
        return self._data.get("threadId")

    def snippet(self) -> str:
        return self._data.get("snippet", "")

    def label_ids(self) -> list[str]:
        return list(self._data.get("labelIds", []))

    def headers(self) -> dict[str, str]:
        payload = self._data.get("payload", {})
        raw_headers = payload.get("headers", []) or []
        collected: dict[str, str] = {}
        for item in raw_headers:
            name = item.get("name")
            value = item.get("value")
            if name and value is not None:
                collected[name] = str(value)
        return collected

    def header(self, name: str, default: str | None = None) -> str | None:
        target = name.strip().lower()
        if not target:
            return default
        payload = self._data.get("payload", {})
        raw_headers = payload.get("headers", []) or []
        for item in raw_headers:
            header_name = str(item.get("name", "")).lower()
            if header_name == target:
                value = item.get("value")
                return str(value) if value is not None else default
        return default

    def subject(self) -> str:
        return self.header("Subject", "") or ""

    def sender(self) -> str:
        return self.header("From", "") or ""

    def to(self) -> str:
        return self.header("To", "") or ""

    def cc(self) -> str:
        return self.header("Cc", "") or ""

    def bcc(self) -> str:
        return self.header("Bcc", "") or ""

    @staticmethod
    def _decode_base64url(data: str) -> str:
        if not data:
            return ""
        padded = data + "=" * (-len(data) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        return decoded.decode("utf-8", errors="replace")

    def _extract_text_parts(self) -> dict[str, str]:
        if self._text_parts_cache is not None:
            return self._text_parts_cache

        found: dict[str, str] = {}

        def walk(part: dict[str, Any]):
            mime_type = str(part.get("mimeType", "")).lower()
            body = part.get("body", {}) or {}
            data = body.get("data")
            if data and mime_type.startswith("text/"):
                found[mime_type] = self._decode_base64url(str(data))
            for child in part.get("parts", []) or []:
                walk(child)

        payload = self._data.get("payload", {}) or {}
        walk(payload)
        self._text_parts_cache = found
        return found

    def plain_body(self) -> str:
        text_parts = self._extract_text_parts()
        return text_parts.get("text/plain", "")

    def html_body(self) -> str:
        text_parts = self._extract_text_parts()
        return text_parts.get("text/html", "")

    def body(self, prefer_html: bool = False, fallback_to_snippet: bool = True) -> str:
        plain = self.plain_body()
        html = self.html_body()
        if prefer_html and html:
            return html
        if plain:
            return plain
        if html:
            return html
        if fallback_to_snippet:
            return self.snippet()
        return ""

    def received_at(self) -> datetime | None:
        internal_date = self._data.get("internalDate")
        if internal_date:
            try:
                return datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc)
            except (TypeError, ValueError):
                pass

        date_header = self.header("Date")
        if date_header:
            try:
                parsed = parsedate_to_datetime(date_header)
                if parsed and parsed.tzinfo is None:
                    return parsed.replace(tzinfo=timezone.utc)
                return parsed
            except (TypeError, ValueError):
                pass
        return None

    def receipt_time(self) -> datetime | None:
        return self.received_at()

    def has_attachments(self) -> bool:
        def walk(part: dict[str, Any]) -> bool:
            body = part.get("body", {}) or {}
            if body.get("attachmentId"):
                return True
            return any(walk(child) for child in part.get("parts", []) or [])

        payload = self._data.get("payload", {}) or {}
        return walk(payload)


class GmailReader:

    def __init__(self):
        """Shows basic usage of the Gmail API.
        Lists the user's Gmail labels.
        """
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file(
                "token.json",
                SCOPES
            )
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("token.json", "w") as token:
                token.write(creds.to_json())

        # Call the Gmail API
        self.service = build("gmail", "v1", credentials=creds)

    def _list_message_refs(
        self,
        q: Union[str, GmailQueryBuilder],
        max_results: int = 25,
        label_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        query = str(q).strip()
        results = self.service.users().messages().list(
            userId="me",
            labelIds=label_ids or ["INBOX"],
            q=query,
            maxResults=max_results,
        ).execute()
        return results.get("messages", [])

    def get_message(self, message_id: str, format: str = "full") -> GmailMessage:
        response = self.service.users().messages().get(
            userId="me",
            id=message_id,
            format=format,
        ).execute()
        return GmailMessage(response)

    def list_message_ids(
        self,
        q: Union[str, GmailQueryBuilder],
        max_results: int = 25,
        label_ids: list[str] | None = None,
    ) -> list[str]:
        refs = self._list_message_refs(q=q, max_results=max_results, label_ids=label_ids)
        return [item["id"] for item in refs if item.get("id")]

    def get_messages(
        self,
        q: Union[str, GmailQueryBuilder],
        max_results: int = 25,
        label_ids: list[str] | None = None,
        time_delta: timedelta | None = None,
    ) -> list[GmailMessage]:
        refs = self._list_message_refs(q=q, max_results=max_results, label_ids=label_ids)
        messages: list[GmailMessage] = []
        for item in refs:
            message_id = item.get("id")
            if message_id:
                messages.append(self.get_message(message_id))

        if time_delta is None:
            return messages
        if time_delta.total_seconds() < 0:
            raise ValueError("time_delta must be greater than or equal to zero.")

        cutoff = datetime.now(timezone.utc) - time_delta
        filtered: list[GmailMessage] = []
        for message in messages:
            received_at = message.received_at()
            if received_at is not None and received_at >= cutoff:
                filtered.append(message)
        return filtered


if __name__ == "__main__":
    pass
