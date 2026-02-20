from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from collections.abc import Callable

import requests

MAX_EMBEDS_PER_WEBHOOK = 10


def _drop_none(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {
            key: _drop_none(item)
            for key, item in value.items()
            if item is not None and item != [] and item != {}
        }
        return cleaned
    if isinstance(value, list):
        return [_drop_none(item) for item in value if item is not None]
    return value


@dataclass
class Author:
    name: str | None = None
    url: str | None = None
    icon_url: str | None = None

    @staticmethod
    def from_dict(obj: dict[str, Any] | None) -> Author | None:
        if not obj:
            return None
        return Author(
            name=obj.get("name"),
            url=obj.get("url"),
            icon_url=obj.get("icon_url"),
        )


@dataclass
class Field:
    name: str | None = None
    value: str | None = None
    inline: bool = False

    @staticmethod
    def from_dict(obj: dict[str, Any] | None) -> Field | None:
        if not obj:
            return None
        return Field(
            name=obj.get("name"),
            value=obj.get("value"),
            inline=bool(obj.get("inline", False)),
        )


@dataclass
class Footer:
    text: str | None = None
    icon_url: str | None = None

    @staticmethod
    def from_dict(obj: dict[str, Any] | None) -> Footer | None:
        if not obj:
            return None
        return Footer(
            text=obj.get("text"),
            icon_url=obj.get("icon_url"),
        )


@dataclass
class Image:
    url: str

    @staticmethod
    def from_dict(obj: dict[str, Any] | None) -> Image | None:
        if not obj or not obj.get("url"):
            return None
        return Image(url=obj["url"])


@dataclass
class Thumbnail:
    url: str

    @staticmethod
    def from_dict(obj: dict[str, Any] | None) -> Thumbnail | None:
        if not obj or not obj.get("url"):
            return None
        return Thumbnail(url=obj["url"])


@dataclass
class Embed:
    title: str | None = None
    description: str | None = None
    url: str | None = None
    color: int | None = None
    fields: list[Field] = field(default_factory=list)
    author: Author | None = None
    footer: Footer | None = None
    image: Image | None = None
    thumbnail: Thumbnail | None = None

    @staticmethod
    def from_dict(obj: dict[str, Any] | None) -> Embed | None:
        if not obj:
            return None
        return Embed(
            title=obj.get("title"),
            description=obj.get("description"),
            url=obj.get("url"),
            color=obj.get("color"),
            fields=[item for item in (Field.from_dict(y) for y in obj.get("fields", [])) if item],
            author=Author.from_dict(obj.get("author")),
            footer=Footer.from_dict(obj.get("footer")),
            image=Image.from_dict(obj.get("image")),
            thumbnail=Thumbnail.from_dict(obj.get("thumbnail")),
        )


@dataclass
class Root:
    content: str | None = None
    embeds: list[Embed] = field(default_factory=list)
    username: str | None = None
    avatar_url: str | None = None
    attachments: list[object] = field(default_factory=list)

    @staticmethod
    def from_dict(obj: dict[str, Any] | None) -> Root | None:
        if not obj:
            return None
        return Root(
            content=obj.get("content"),
            embeds=[item for item in (Embed.from_dict(y) for y in obj.get("embeds", [])) if item],
            username=obj.get("username"),
            avatar_url=obj.get("avatar_url"),
            attachments=obj.get("attachments", []),
        )

    def to_payload(self) -> dict[str, Any]:
        return _drop_none(asdict(self))


def build_email_embed(message_id: str, subject: str, summary: str) -> Embed:
    return Embed(
        title=subject,
        url="https://mail.google.com/mail/u/0/#inbox/" + message_id,
        description=summary,
        color=15258703,
    )


def send_webhook(
    embeds: list[Embed],
    url: str,
    content: str | None = "I have messages you might be interested in.\n\n",
) -> requests.Response:
    if not url:
        raise ValueError("Discord webhook URL is required.")
    if len(embeds) > MAX_EMBEDS_PER_WEBHOOK:
        raise ValueError(
            f"Discord webhook messages support a maximum of {MAX_EMBEDS_PER_WEBHOOK} embeds."
        )

    hook = Root(content=content, embeds=embeds)

    response = requests.post(
        url=url,
        json=hook.to_payload(),
        timeout=10,
    )
    response.raise_for_status()
    return response


def send_webhook_chunked(
    embeds: list[Embed],
    url: str,
    content: str | None = "I have messages you might be interested in.\n\n",
    chunk_size: int = MAX_EMBEDS_PER_WEBHOOK,
) -> list[requests.Response]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0.")

    responses: list[requests.Response] = []
    for start in range(0, len(embeds), chunk_size):
        chunk = embeds[start:start + chunk_size]
        chunk_content = content if start == 0 else None
        responses.append(send_webhook(embeds=chunk, url=url, content=chunk_content))
    return responses


def make_notifier(message_id: str, subject: str) -> Callable[[str], Embed]:
    def notify(summary: str) -> Embed:
        return build_email_embed(
            message_id=message_id,
            subject=subject,
            summary=summary,
        )
    return notify
