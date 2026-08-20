"""Single-flight private-message transport between AstrBot and Yurisaki."""

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

PRIVATE_MESSAGE_EVENT = "message.private"


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

    def __post_init__(self) -> None:
        if not self.yurisaki_user_id.isdecimal():
            raise ValueError("yurisaki_user_id must contain digits only")
        if not self.self_id.isdecimal():
            raise ValueError("self_id must contain digits only")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self.min_request_interval < 0:
            raise ValueError("min_request_interval cannot be negative")


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
        self._started = False
        self._shutting_down = False
        self._event_handler = self._on_private_event

    @property
    def pending(self) -> PendingRequest | None:
        """Expose pending state for diagnostics without allowing mutation."""
        return self._pending

    @property
    def is_running(self) -> bool:
        return self._started and not self._shutting_down

    def start(self) -> None:
        """Register exactly one raw private-message callback."""
        if self._started:
            return
        self._shutting_down = False
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
            return

        self._shutting_down = True
        self._started = False
        pending = self._pending
        if pending is not None and not pending.future.done():
            pending.future.set_exception(
                TransportShuttingDownError("Yurisaki transport is shutting down")
            )
        self._client.unsubscribe(PRIVATE_MESSAGE_EVENT, self._event_handler)

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

        pending = self._pending
        if pending is None or pending.future.done():
            return False
        if (
            event.get("post_type") != "message"
            or event.get("message_type") != "private"
        ):
            return False
        if _string_id(event.get("user_id")) != pending.expected_sender_id:
            return False
        if _string_id(event.get("self_id")) != pending.expected_self_id:
            return False

        event_time = event.get("time")
        if not isinstance(event_time, (int, float)) or event_time < pending.sent_at:
            return False
        message = event.get("message")
        if not isinstance(message, list) or not _has_text_segment(message):
            return False

        pending.future.set_result(list(message))
        return True


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
