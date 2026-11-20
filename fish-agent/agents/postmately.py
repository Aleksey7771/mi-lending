"""Postmately MCP client for validated Telegram publishing."""
import json
from dataclasses import dataclass
from typing import Any

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError


class PostmatelyError(RuntimeError):
    def __init__(self, message: str, *, outcome_uncertain: bool = False) -> None:
        super().__init__(message)
        self.outcome_uncertain = outcome_uncertain


@dataclass(frozen=True)
class PostmatelyPost:
    post_id: str
    status: str


class PostmatelyClient:
    def __init__(
        self,
        *,
        url: str | None = None,
        api_key: str | None = None,
        telegram_channel_id: str | None = None,
    ) -> None:
        defaults = ("", "", "")
        if url is None or api_key is None or telegram_channel_id is None:
            from config import settings

            defaults = (
                settings.postmately_mcp_url,
                settings.postmately_api_key,
                settings.postmately_telegram_channel_id,
            )
        self._url = url if url is not None else defaults[0]
        self._api_key = api_key if api_key is not None else defaults[1]
        self._telegram_channel_id = (
            telegram_channel_id if telegram_channel_id is not None else defaults[2]
        )
        if not self._url:
            raise PostmatelyError("Postmately MCP URL is not configured")
        if not self._api_key:
            raise PostmatelyError("POSTMATELY_API_KEY is not configured")

    async def _call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        outcome_uncertain: bool = False,
    ) -> Any:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        call_started = False
        try:
            async with httpx2.AsyncClient(headers=headers, timeout=30.0) as http_client:
                async with streamable_http_client(
                    self._url,
                    http_client=http_client,
                ) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        call_started = True
                        result = await session.call_tool(name, arguments)
        except PostmatelyError:
            raise
        except (httpx2.HTTPError, MCPError) as error:
            raise PostmatelyError(
                f"Postmately MCP call '{name}' failed",
                outcome_uncertain=outcome_uncertain and call_started,
            ) from error

        payload = _decode_tool_result(result)
        if getattr(result, "isError", False):
            raise PostmatelyError(
                f"Postmately tool '{name}' returned an error: {_summarize(payload)}",
                outcome_uncertain=outcome_uncertain,
            )
        return payload

    async def validate_telegram_post(self, text: str) -> str:
        channels_payload = await self._call_tool("list_channels")
        channels = _as_list(channels_payload, "channels")
        telegram_channels = [
            channel
            for channel in channels
            if isinstance(channel, dict)
            and channel.get("platform") == "telegram"
            and channel.get("canPublish") is True
        ]

        if self._telegram_channel_id:
            telegram_channels = [
                channel
                for channel in telegram_channels
                if channel.get("id") == self._telegram_channel_id
            ]
        if not telegram_channels:
            raise PostmatelyError(
                "No publishable Telegram channel is connected in Postmately"
            )
        if len(telegram_channels) != 1:
            raise PostmatelyError(
                "More than one Telegram channel can publish; set "
                "POSTMATELY_TELEGRAM_CHANNEL_ID"
            )

        channel_id = telegram_channels[0].get("id")
        if not isinstance(channel_id, str) or not channel_id:
            raise PostmatelyError("Postmately returned a Telegram channel without an ID")

        validation = await self._call_tool(
            "validate_post",
            {"text": text, "channels": [channel_id]},
        )
        if not isinstance(validation, dict) or validation.get("ok") is not True:
            issues = validation.get("issues", []) if isinstance(validation, dict) else []
            raise PostmatelyError(
                f"Postmately rejected the Telegram post: {_summarize(issues)}"
            )
        return channel_id

    async def publish_telegram_post(self, text: str, channel_id: str) -> PostmatelyPost:
        payload = await self._call_tool(
            "create_post",
            {"text": text, "channels": [channel_id], "when": "now"},
            outcome_uncertain=True,
        )
        if not isinstance(payload, dict):
            raise PostmatelyError(
                "Postmately returned an invalid create_post response",
                outcome_uncertain=True,
            )
        post_id = payload.get("id")
        if not isinstance(post_id, str) or not post_id:
            raise PostmatelyError(
                "Postmately created a post but returned no post ID",
                outcome_uncertain=True,
            )
        return PostmatelyPost(post_id=post_id, status=str(payload.get("status", "unknown")))


def _decode_tool_result(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured

    text_blocks = [
        block.text for block in getattr(result, "content", []) if isinstance(
            getattr(block, "text", None), str
        )
    ]
    if len(text_blocks) == 1:
        try:
            return json.loads(text_blocks[0])
        except json.JSONDecodeError:
            return text_blocks[0]
    return text_blocks


def _as_list(payload: Any, label: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get(label), list):
        return payload[label]
    raise PostmatelyError(f"Postmately returned an invalid {label} response")


def _summarize(value: Any) -> str:
    if isinstance(value, str):
        return value[:500]
    return json.dumps(value, ensure_ascii=False, default=str)[:500]
