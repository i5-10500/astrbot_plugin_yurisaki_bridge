# SPDX-FileCopyrightText: 2026 i5-10500
# SPDX-License-Identifier: AGPL-3.0-or-later

"""AstrBot plugin entry point for Yurisaki Bridge."""

import asyncio
import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from .yurisaki_bridge import __version__
from .yurisaki_bridge.models import RandomSongResult
from .yurisaki_bridge.service import (
    YurisakiService,
    random_song_error,
    unavailable_payload,
)
from .yurisaki_bridge.transport import TransportConfig, YurisakiTransport

_PLATFORM_NAME = "aiocqhttp"
_RANDOM_TOOL_EVENT_KEY = "yurisaki_bridge.random_song_called"


class YurisakiBridgePlugin(Star):
    """Own AstrBot registration, lazy transport setup, and lifecycle cleanup."""

    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config
        self._transport: YurisakiTransport | None = None
        self._service: YurisakiService | None = None
        self._setup_lock = asyncio.Lock()
        self._terminated = False

    async def initialize(self) -> None:
        """Attempt eager setup while retaining lazy recovery for late connections."""
        if not self.config.get("enabled", True):
            logger.info("Yurisaki Bridge %s is disabled by configuration", __version__)
            return
        try:
            await self._ensure_service()
        except Exception as exc:
            logger.warning(
                "Yurisaki Bridge %s is waiting for aiocqhttp: %s",
                __version__,
                exc,
            )

    @filter.llm_tool(name="yurisaki_song_info")
    async def yurisaki_song_info(
        self,
        event: AstrMessageEvent,
        query: str,
    ) -> str:
        """查询 Yurisaki 的 Arcaea 曲目信息；仅执行固定的 /a info 命令。

        Args:
            query(string): 曲名、曲目别名或曲目 ID，长度不超过 120 个字符
        """
        del event
        if not self.config.get("enabled", True):
            payload = unavailable_payload(query, "Yurisaki Bridge is disabled.")
            return json.dumps(payload, ensure_ascii=False)

        try:
            service = await self._ensure_service()
        except Exception:
            logger.warning("Unable to initialize Yurisaki transport", exc_info=True)
            payload = unavailable_payload(
                query,
                "No connected aiocqhttp platform is available.",
            )
            return json.dumps(payload, ensure_ascii=False)

        payload = await service.song_info(query)
        return json.dumps(payload, ensure_ascii=False)

    @filter.llm_tool(name="yurisaki_random_song")
    async def yurisaki_random_song(self, event: AstrMessageEvent) -> str:
        """随机推荐一首 Arcaea 曲目并发送封面；不支持筛选，每轮最多调用一次。"""
        if not self.config.get("enabled", True):
            result = random_song_error(
                "transport_unavailable",
                "Yurisaki Bridge is disabled.",
            )
            return json.dumps(result.to_dict(), ensure_ascii=False)

        if event.get_extra(_RANDOM_TOOL_EVENT_KEY):
            result = random_song_error(
                "duplicate_tool_call",
                "The random-song Tool was already called for this user request.",
            )
            return json.dumps(result.to_dict(), ensure_ascii=False)
        event.set_extra(_RANDOM_TOOL_EVENT_KEY, True)

        try:
            service = await self._ensure_service()
        except Exception:
            logger.warning("Unable to initialize Yurisaki transport", exc_info=True)
            result = random_song_error(
                "transport_unavailable",
                "No connected aiocqhttp platform is available.",
            )
            return json.dumps(result.to_dict(), ensure_ascii=False)

        result = await service.random_song()
        if result.ok:
            await self._deliver_random_image(event, result)
        return json.dumps(result.to_dict(), ensure_ascii=False)

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP, priority=1000)
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE, priority=1000)
    async def intercept_yurisaki_response(self, event: AstrMessageEvent) -> None:
        """Stop a response consumed by the bridge from entering normal chat flow."""
        transport = self._transport
        if transport is None or not transport.is_running:
            return
        raw_event = event.message_obj.raw_message
        consumed_now = await transport.consume_event(raw_event)
        if consumed_now or transport.was_consumed(raw_event):
            event.stop_event()

    async def terminate(self) -> None:
        """Release the raw callback and fail any pending request safely."""
        self._terminated = True
        transport = self._transport
        self._service = None
        self._transport = None
        if transport is not None:
            await transport.shutdown()
        logger.info("Yurisaki Bridge terminated")

    async def _deliver_random_image(
        self,
        event: AstrMessageEvent,
        result: RandomSongResult,
    ) -> None:
        image_source = next(
            (
                safe_url
                for image in result.images
                if (safe_url := _safe_image_url(image.url))
            ),
            None,
        )
        if image_source is None:
            return
        try:
            await event.send(event.image_result(image_source))
        except Exception:
            logger.warning("Unable to deliver the Yurisaki random-song image")
            return
        result.image_delivered = True

    async def _ensure_service(self) -> YurisakiService:
        if self._terminated:
            raise RuntimeError("plugin is shutting down")
        if self._service is not None and self._transport is not None:
            if self._transport.is_running:
                return self._service

        async with self._setup_lock:
            if self._terminated:
                raise RuntimeError("plugin is shutting down")
            if self._service is not None and self._transport is not None:
                if self._transport.is_running:
                    return self._service

            platform = self._select_platform()
            client = platform.get_client()
            login_info = await client.call_action("get_login_info")
            if self._terminated:
                raise RuntimeError("plugin is shutting down")
            self_id = _login_user_id(login_info)
            transport_config = TransportConfig(
                yurisaki_user_id=str(self.config.get("yurisaki_user_id", "3889054356")),
                self_id=self_id,
                timeout_seconds=float(self.config.get("timeout_seconds", 15.0)),
                min_request_interval=float(
                    self.config.get("min_request_interval", 2.0)
                ),
                timeout_quarantine_seconds=float(
                    self.config.get("timeout_quarantine_seconds", 5.0)
                ),
            )
            transport = YurisakiTransport(client, transport_config)
            transport.start()
            self._transport = transport
            self._service = YurisakiService(transport)
            if self.config.get("debug_logging", False):
                logger.info(
                    "Yurisaki transport connected through platform %s",
                    platform.meta().id,
                )
            return self._service

    def _select_platform(self) -> Any:
        configured_id = str(self.config.get("platform_id", "")).strip()
        candidates = [
            platform
            for platform in self.context.platform_manager.get_insts()
            if platform.meta().name == _PLATFORM_NAME
            and (not configured_id or platform.meta().id == configured_id)
        ]
        if not candidates:
            raise RuntimeError("matching aiocqhttp platform was not found")
        if len(candidates) > 1:
            raise RuntimeError("platform_id is required when multiple platforms exist")
        return candidates[0]


def _login_user_id(login_info: object) -> str:
    if not isinstance(login_info, Mapping):
        raise RuntimeError("get_login_info returned an invalid response")
    user_id = login_info.get("user_id")
    if not isinstance(user_id, (int, str)) or not str(user_id).isdecimal():
        raise RuntimeError("get_login_info did not return a valid user_id")
    return str(user_id)


def _safe_image_url(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return value
