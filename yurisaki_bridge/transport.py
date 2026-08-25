# SPDX-FileCopyrightText: 2026 i5-10500
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Single-flight private-message transport between AstrBot and Yurisaki."""

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

PRIVATE_MESSAGE_EVENT = "message.private"
_CONSUMED_EVENT_TTL_SECONDS = 30.0
_MAX_CONSUMED_EVENTS = 32


class AiocqhttpClient(Protocol):
    """The supported subset of ``aiocqhttp.CQHttp``."""

    def subscribe(self, event_name: str, handler: Callable[..., object]) -> None: ...

    def unsubscribe(self, event_name: str, handler: Callable[..., object]) -> None: ...

    async def call_action(self, action: str, **params: object) -> Any: ...


class TransportError(RuntimeError):
    """Base class for safe, expected transport failures."""


class TransportUnavailableError(TransportError):
    """Raised when the transport is not running."""


class SendFailedError(TransportError):
    """Raised when OneBot rejects or cannot send a command."""


class ResponseTimeoutError(TransportError):
    """Raised when Yurisaki does not respond within the configured timeout."""


class TransportShuttingDownError(TransportError):
    """Raised when an active request is interrupted by plugin shutdown."""


@dataclass(frozen=True, slots=True)
class TransportConfig:
    """Validated transport settings."""

    yurisaki_user_id: str
    self_id: str
    timeout_seconds: float = 15.0
    min_request_interval: float = 2.0
    timeout_quarantine_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not self.yurisaki_user_id.isdecimal():
            raise ValueError("yurisaki_user_id must contain digits only")
        if not self.self_id.isdecimal():
            raise ValueError("self_id must contain digits only")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self.min_request_interval < 0:
            raise ValueError("min_request_interval cannot be negative")
        if self.timeout_quarantine_seconds < 0:
            raise ValueError("timeout_quarantine_seconds cannot be negative")


@dataclass(slots=True)
class PendingRequest:
    """The only request eligible to consume a raw private response."""

    command: str
    created_at: float
    sent_at: int
    expected_sender_id: str
    expected_self_id: str
    future: asyncio.Future[list[object]]


class YurisakiTransport:
    """Serialize commands and match one strictly filtered private response."""

    def __init__(
        self,
        client: AiocqhttpClient,
        config: TransportConfig,
        *,
        wall_clock: Callable[[], float] = time.time,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = client
        self._config = config
        self._wall_clock = wall_clock
        self._monotonic = monotonic
        self._sleep = sleep
        self._request_lock = asyncio.Lock()
        self._pending: PendingRequest | None = None
        self._last_sent_at: float | None = None
        self._quarantine_until: float | None = None
        self._quarantine_changed = asyncio.Event()
        self._started = False
        self._shutting_down = False
        self._event_handler = self._on_private_event
        self._consumed_events: deque[tuple[float, tuple[str, str, str, str]]] = deque(
            maxlen=_MAX_CONSUMED_EVENTS
        )

    @property
    def pending(self) -> PendingRequest | None:
        """Expose pending state for diagnostics without allowing mutation."""
        return self._pending

    @property
    def is_running(self) -> bool:
        return self._started and not self._shutting_down

    @property
    def is_quarantined(self) -> bool:
        """Return whether a timed-out response can still contaminate a request."""
        return self._quarantine_remaining() > 0

    def start(self) -> None:
        """Register exactly one raw private-message callback."""
        if self._started:
            return
        self._shutting_down = False
        self._quarantine_until = None
        self._quarantine_changed.clear()
        self._consumed_events.clear()
        self._client.subscribe(PRIVATE_MESSAGE_EVENT, self._event_handler)
        self._started = True

    async def request(self, command: str) -> list[object]:
        """Send one controlled command and await its matching raw response."""
        if not self.is_running:
            raise TransportUnavailableError("Yurisaki transport is not running")

        async with self._request_lock:
            if not self.is_running:
                raise TransportUnavailableError("Yurisaki transport is not running")

            await self._respect_request_interval()
            await self._wait_for_quarantine()
            loop = asyncio.get_running_loop()
            pending = PendingRequest(
                command=command,
                created_at=self._wall_clock(),
                sent_at=int(self._wall_clock()),
                expected_sender_id=self._config.yurisaki_user_id,
                expected_self_id=self._config.self_id,
                future=loop.create_future(),
            )
            self._pending = pending

            try:
                try:
                    await self._client.call_action(
                        "send_private_msg",
                        user_id=int(self._config.yurisaki_user_id),
                        message=command,
                    )
                except Exception as exc:
                    raise SendFailedError("Failed to send command to Yurisaki") from exc

                self._last_sent_at = self._monotonic()
                try:
                    return await asyncio.wait_for(
                        pending.future,
                        timeout=self._config.timeout_seconds,
                    )
                except TimeoutError as exc:
                    self._enter_quarantine()
                    raise ResponseTimeoutError(
                        "Yurisaki did not respond before the timeout"
                    ) from exc
            finally:
                if self._pending is pending:
                    self._pending = None
                if not pending.future.done():
                    pending.future.cancel()

    async def shutdown(self) -> None:
        """Make callbacks inert, cancel pending work, and unregister cleanly."""
        if not self._started:
            self._shutting_down = True
            self._quarantine_until = None
            self._quarantine_changed.set()
            return

        self._shutting_down = True
        self._started = False
        self._quarantine_until = None
        self._quarantine_changed.set()
        pending = self._pending
        if pending is not None and not pending.future.done():
            pending.future.set_exception(
                TransportShuttingDownError("Yurisaki transport is shutting down")
            )
        self._client.unsubscribe(PRIVATE_MESSAGE_EVENT, self._event_handler)
        self._consumed_events.clear()

    async def _wait_for_quarantine(self) -> None:
        while True:
            if self._shutting_down:
                raise TransportShuttingDownError("Yurisaki transport is shutting down")
            if not self._started:
                raise TransportUnavailableError("Yurisaki transport is not running")

            remaining = self._quarantine_remaining()
            if remaining <= 0:
                return

            self._quarantine_changed.clear()
            sleep_task = asyncio.ensure_future(self._sleep(remaining))
            change_task = asyncio.create_task(self._quarantine_changed.wait())
            try:
                await asyncio.wait(
                    {sleep_task, change_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
            finally:
                for task in (sleep_task, change_task):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(sleep_task, change_task, return_exceptions=True)

    def _enter_quarantine(self) -> None:
        duration = self._config.timeout_quarantine_seconds
        if duration <= 0:
            return
        self._quarantine_until = self._monotonic() + duration
        self._quarantine_changed.set()

    def _extend_quarantine(self) -> None:
        duration = self._config.timeout_quarantine_seconds
        if duration <= 0:
            return
        new_deadline = self._monotonic() + duration
        self._quarantine_until = max(self._quarantine_until or 0.0, new_deadline)
        self._quarantine_changed.set()

    def _quarantine_remaining(self) -> float:
        if self._quarantine_until is None:
            return 0.0
        remaining = self._quarantine_until - self._monotonic()
        if remaining <= 0:
            self._quarantine_until = None
            return 0.0
        return remaining

    async def _respect_request_interval(self) -> None:
        if self._last_sent_at is None:
            return
        remaining = self._config.min_request_interval - (
            self._monotonic() - self._last_sent_at
        )
        if remaining > 0:
            await self._sleep(remaining)

    async def _on_private_event(self, event: object) -> None:
        await self.consume_event(event)

    async def consume_event(self, event: object) -> bool:
        """Resolve the active request only for a strict matching event."""
        if not self.is_running or not isinstance(event, Mapping):
            return False
        if (
            event.get("post_type") != "message"
            or event.get("message_type") != "private"
        ):
            return False
        if _string_id(event.get("user_id")) != self._config.yurisaki_user_id:
            return False
        if _string_id(event.get("self_id")) != self._config.self_id:
            return False

        if self.is_quarantined:
            self._extend_quarantine()
            self._record_consumed_event(event)
            return True

        pending = self._pending
        if pending is None or pending.future.done():
            return False

        event_time = event.get("time")
        if not isinstance(event_time, (int, float)) or event_time < pending.sent_at:
            return False
        message = event.get("message")
        if not isinstance(message, list) or not _has_text_segment(message):
            return False

        pending.future.set_result(list(message))
        self._record_consumed_event(event)
        return True

    def was_consumed(self, event: object) -> bool:
        """Return whether this raw event recently resolved the active request."""
        if not isinstance(event, Mapping):
            return False
        self._prune_consumed_events()
        event_key = _event_key(event)
        return event_key is not None and any(
            consumed_key == event_key for _, consumed_key in self._consumed_events
        )

    def _prune_consumed_events(self) -> None:
        cutoff = self._monotonic() - _CONSUMED_EVENT_TTL_SECONDS
        while self._consumed_events and self._consumed_events[0][0] < cutoff:
            self._consumed_events.popleft()

    def _record_consumed_event(self, event: Mapping[object, object]) -> None:
        event_key = _event_key(event)
        if event_key is not None:
            self._consumed_events.append((self._monotonic(), event_key))


def _string_id(value: object) -> str | None:
    if isinstance(value, (int, str)):
        return str(value)
    return None


def _has_text_segment(message: list[object]) -> bool:
    for segment in message:
        if not isinstance(segment, Mapping) or segment.get("type") != "text":
            continue
        data = segment.get("data")
        if isinstance(data, Mapping):
            text = data.get("text")
            if isinstance(text, str) and text.strip():
                return True
    return False


def _event_key(event: Mapping[object, object]) -> tuple[str, str, str, str] | None:
    message_id = _string_id(event.get("message_id"))
    user_id = _string_id(event.get("user_id"))
    self_id = _string_id(event.get("self_id"))
    event_time = _string_id(event.get("time"))
    if None in (message_id, user_id, self_id, event_time):
        return None
    return message_id, user_id, self_id, event_time  # type: ignore[return-value]
