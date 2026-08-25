"""Offline tests for the single-flight OneBot transport."""

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from yurisaki_bridge.transport import (
    PRIVATE_MESSAGE_EVENT,
    ResponseTimeoutError,
    SendFailedError,
    TransportConfig,
    TransportShuttingDownError,
    TransportUnavailableError,
    YurisakiTransport,
)

BOT_ID = "100001"
YURISAKI_ID = "200002"


class FakeClient:
    def __init__(self) -> None:
        self.handlers: dict[str, list[Callable[..., object]]] = {}
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.call_events: asyncio.Queue[None] = asyncio.Queue()
        self.send_error: Exception | None = None

    def subscribe(self, event_name: str, handler: Callable[..., object]) -> None:
        self.handlers.setdefault(event_name, []).append(handler)

    def unsubscribe(self, event_name: str, handler: Callable[..., object]) -> None:
        self.handlers[event_name].remove(handler)

    async def call_action(self, action: str, **params: object) -> Any:
        self.calls.append((action, params))
        self.call_events.put_nowait(None)
        if self.send_error is not None:
            raise self.send_error
        return {"message_id": 1}

    async def emit(self, event: object) -> list[object]:
        results = []
        for handler in list(self.handlers.get(PRIVATE_MESSAGE_EVENT, [])):
            results.append(await handler(event))
        return results


class ManualClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleep_calls: asyncio.Queue[float] = asyncio.Queue()
        self._sleepers: list[tuple[float, asyncio.Future[None]]] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        future = asyncio.get_running_loop().create_future()
        self._sleepers.append((self.now + delay, future))
        self.sleep_calls.put_nowait(delay)
        await future

    def advance(self, seconds: float) -> None:
        self.now += seconds
        for deadline, future in self._sleepers:
            if deadline <= self.now and not future.done():
                future.set_result(None)
        self._sleepers = [
            (deadline, future)
            for deadline, future in self._sleepers
            if not future.done()
        ]

    async def wait_for_sleep(self) -> float:
        async with asyncio.timeout(0.2):
            return await self.sleep_calls.get()


def _config(**overrides: object) -> TransportConfig:
    values = {
        "yurisaki_user_id": YURISAKI_ID,
        "self_id": BOT_ID,
        "timeout_seconds": 0.2,
        "min_request_interval": 0.0,
        "timeout_quarantine_seconds": 0.0,
    }
    values.update(overrides)
    return TransportConfig(**values)  # type: ignore[arg-type]


def _event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "post_type": "message",
        "message_type": "private",
        "user_id": int(YURISAKI_ID),
        "self_id": int(BOT_ID),
        "time": 1_000,
        "message_id": 123,
        "message": [{"type": "text", "data": {"text": "曲目: Test"}}],
    }
    event.update(overrides)
    return event


async def _wait_for_calls(client: FakeClient, count: int) -> None:
    async with asyncio.timeout(0.2):
        while len(client.calls) < count:
            await client.call_events.get()


@pytest.mark.asyncio
async def test_start_and_shutdown_manage_one_callback() -> None:
    client = FakeClient()
    transport = YurisakiTransport(client, _config())

    transport.start()
    transport.start()
    assert len(client.handlers[PRIVATE_MESSAGE_EVENT]) == 1

    await transport.shutdown()
    assert client.handlers[PRIVATE_MESSAGE_EVENT] == []
    assert transport.is_running is False


@pytest.mark.asyncio
async def test_request_sends_private_message_and_returns_segments() -> None:
    client = FakeClient()
    transport = YurisakiTransport(client, _config(), wall_clock=lambda: 1_000.5)
    transport.start()

    task = asyncio.create_task(transport.request("/a info test"))
    await _wait_for_calls(client, 1)
    callback_results = await client.emit(_event())

    assert callback_results == [None]
    assert await task == _event()["message"]
    assert client.calls == [
        (
            "send_private_msg",
            {"user_id": int(YURISAKI_ID), "message": "/a info test"},
        )
    ]
    assert transport.pending is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "wrong_event",
    [
        _event(user_id=999),
        _event(self_id=999),
        _event(message_type="group"),
        _event(post_type="notice"),
        _event(time=999),
        _event(message=[{"type": "image", "data": {"file": "cover"}}]),
    ],
)
async def test_non_matching_events_are_ignored(wrong_event: object) -> None:
    client = FakeClient()
    transport = YurisakiTransport(client, _config(), wall_clock=lambda: 1_000.5)
    transport.start()

    task = asyncio.create_task(transport.request("/a info test"))
    await _wait_for_calls(client, 1)

    assert await client.emit(wrong_event) == [None]
    assert task.done() is False
    await client.emit(_event())
    await task


@pytest.mark.asyncio
async def test_rand_requires_active_pending() -> None:
    client = FakeClient()
    transport = YurisakiTransport(client, _config())
    transport.start()

    assert (
        await transport.consume_event(
            _event(
                message=[
                    {"type": "image", "data": {"file": "cover"}},
                    {"type": "text", "data": {"text": "曲目: Random\nBPM: 180"}},
                ]
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_duplicate_response_is_consumed_once() -> None:
    client = FakeClient()
    transport = YurisakiTransport(client, _config(), wall_clock=lambda: 1_000.0)
    transport.start()
    task = asyncio.create_task(transport.request("/a info test"))
    await _wait_for_calls(client, 1)

    assert await transport.consume_event(_event()) is True
    assert await transport.consume_event(_event()) is False
    assert transport.was_consumed(_event()) is True
    assert transport.was_consumed(_event(message_id=456)) is False
    await task


@pytest.mark.asyncio
async def test_consumed_marker_expires_and_is_cleared_on_shutdown() -> None:
    client = FakeClient()
    now = 10.0
    transport = YurisakiTransport(
        client,
        _config(),
        wall_clock=lambda: 1_000.0,
        monotonic=lambda: now,
    )
    transport.start()
    task = asyncio.create_task(transport.request("/a info test"))
    await _wait_for_calls(client, 1)
    await transport.consume_event(_event())
    await task

    assert transport.was_consumed(_event()) is True
    now = 41.0
    assert transport.was_consumed(_event()) is False

    await transport.shutdown()
    assert transport.was_consumed(_event()) is False


@pytest.mark.asyncio
async def test_timeout_clears_pending_and_late_response_is_ignored() -> None:
    client = FakeClient()
    transport = YurisakiTransport(
        client,
        _config(timeout_seconds=0.01),
        wall_clock=lambda: 1_000.0,
    )
    transport.start()

    with pytest.raises(ResponseTimeoutError):
        await transport.request("/a info test")

    assert transport.pending is None
    assert await transport.consume_event(_event()) is False


@pytest.mark.asyncio
async def test_timeout_enters_quarantine() -> None:
    client = FakeClient()
    clock = ManualClock()
    transport = YurisakiTransport(
        client,
        _config(timeout_seconds=0.01, timeout_quarantine_seconds=5.0),
        wall_clock=lambda: 1_000.0,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    transport.start()

    with pytest.raises(ResponseTimeoutError):
        await transport.request("/a info first")

    assert transport.is_quarantined is True
    assert await transport.consume_event(_event(message_id=124)) is True
    assert transport.was_consumed(_event(message_id=124)) is True


@pytest.mark.asyncio
async def test_new_request_waits_for_quarantine() -> None:
    client = FakeClient()
    clock = ManualClock()
    transport = YurisakiTransport(
        client,
        _config(timeout_seconds=0.01, timeout_quarantine_seconds=5.0),
        wall_clock=lambda: 1_000.0,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    transport.start()
    with pytest.raises(ResponseTimeoutError):
        await transport.request("/a info first")

    second = asyncio.create_task(transport.request("/a info second"))
    assert await clock.wait_for_sleep() == 5.0
    assert len(client.calls) == 1

    second.cancel()
    with pytest.raises(asyncio.CancelledError):
        await second


@pytest.mark.asyncio
async def test_quarantine_without_late_response_expires() -> None:
    client = FakeClient()
    clock = ManualClock()
    transport = YurisakiTransport(
        client,
        _config(timeout_seconds=0.01, timeout_quarantine_seconds=5.0),
        wall_clock=lambda: 1_000.0,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    transport.start()
    with pytest.raises(ResponseTimeoutError):
        await transport.request("/a info first")

    second = asyncio.create_task(transport.request("/a info second"))
    await clock.wait_for_sleep()
    clock.advance(5.0)
    await _wait_for_calls(client, 2)

    assert transport.is_quarantined is False
    await client.emit(_event(message_id=456))
    await second


@pytest.mark.asyncio
async def test_timeout_then_new_request_then_old_response_arrives() -> None:
    client = FakeClient()
    clock = ManualClock()
    transport = YurisakiTransport(
        client,
        _config(timeout_seconds=0.01, timeout_quarantine_seconds=5.0),
        wall_clock=lambda: 1_000.0,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    transport.start()
    with pytest.raises(ResponseTimeoutError):
        await transport.request("/a info first")

    second = asyncio.create_task(transport.request("/a info second"))
    await clock.wait_for_sleep()
    clock.advance(2.0)
    assert await transport.consume_event(_event(message_id=124)) is True
    assert await clock.wait_for_sleep() == 5.0

    clock.advance(3.0)
    await asyncio.sleep(0)
    assert len(client.calls) == 1
    clock.advance(2.0)
    await _wait_for_calls(client, 2)

    await client.emit(_event(message_id=456))
    assert await second == _event()["message"]


@pytest.mark.asyncio
async def test_multiple_late_responses_extend_quarantine() -> None:
    client = FakeClient()
    clock = ManualClock()
    transport = YurisakiTransport(
        client,
        _config(timeout_seconds=0.01, timeout_quarantine_seconds=5.0),
        wall_clock=lambda: 1_000.0,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    transport.start()
    with pytest.raises(ResponseTimeoutError):
        await transport.request("/a info first")

    second = asyncio.create_task(transport.request("/a info second"))
    await clock.wait_for_sleep()
    clock.advance(1.0)
    assert await transport.consume_event(_event(message_id=124)) is True
    await clock.wait_for_sleep()
    clock.advance(1.0)
    assert await transport.consume_event(_event(message_id=125)) is True
    await clock.wait_for_sleep()

    clock.advance(4.0)
    await asyncio.sleep(0)
    assert len(client.calls) == 1
    clock.advance(1.0)
    await _wait_for_calls(client, 2)
    await client.emit(_event(message_id=456))
    await second


@pytest.mark.asyncio
async def test_shutdown_during_quarantine() -> None:
    client = FakeClient()
    clock = ManualClock()
    transport = YurisakiTransport(
        client,
        _config(timeout_seconds=0.01, timeout_quarantine_seconds=5.0),
        wall_clock=lambda: 1_000.0,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    transport.start()
    with pytest.raises(ResponseTimeoutError):
        await transport.request("/a info first")

    second = asyncio.create_task(transport.request("/a info second"))
    await clock.wait_for_sleep()
    await transport.shutdown()

    with pytest.raises(TransportShuttingDownError):
        await second
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_cancellation_clears_pending() -> None:
    client = FakeClient()
    transport = YurisakiTransport(client, _config())
    transport.start()
    task = asyncio.create_task(transport.request("/a info test"))
    await _wait_for_calls(client, 1)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert transport.pending is None


@pytest.mark.asyncio
async def test_shutdown_interrupts_pending_request() -> None:
    client = FakeClient()
    transport = YurisakiTransport(client, _config())
    transport.start()
    task = asyncio.create_task(transport.request("/a info test"))
    await _wait_for_calls(client, 1)

    await transport.shutdown()

    with pytest.raises(TransportShuttingDownError):
        await task
    assert transport.pending is None


@pytest.mark.asyncio
async def test_send_failure_is_wrapped_and_cleans_pending() -> None:
    client = FakeClient()
    client.send_error = OSError("private network detail")
    transport = YurisakiTransport(client, _config())
    transport.start()

    with pytest.raises(SendFailedError, match="Failed to send"):
        await transport.request("/a info test")
    assert transport.pending is None


@pytest.mark.asyncio
async def test_requests_are_globally_single_flight() -> None:
    client = FakeClient()
    transport = YurisakiTransport(client, _config(), wall_clock=lambda: 1_000.0)
    transport.start()
    first = asyncio.create_task(transport.request("/a info first"))
    second = asyncio.create_task(transport.request("/a info second"))

    await _wait_for_calls(client, 1)
    assert len(client.calls) == 1
    await client.emit(_event())
    await first

    await _wait_for_calls(client, 2)
    assert client.calls[1][1]["message"] == "/a info second"
    await client.emit(_event())
    await second


@pytest.mark.asyncio
async def test_info_and_rand_are_serialized_together() -> None:
    client = FakeClient()
    transport = YurisakiTransport(client, _config(), wall_clock=lambda: 1_000.0)
    transport.start()
    info = asyncio.create_task(transport.request("/a info Test"))
    random_song = asyncio.create_task(transport.request("/a rand"))

    await _wait_for_calls(client, 1)
    assert client.calls[0][1]["message"] == "/a info Test"
    assert len(client.calls) == 1
    await client.emit(_event(message_id=124))
    await info

    await _wait_for_calls(client, 2)
    assert client.calls[1][1]["message"] == "/a rand"
    await client.emit(_event(message_id=125))
    await random_song


@pytest.mark.asyncio
async def test_minimum_request_interval_is_enforced() -> None:
    client = FakeClient()
    now = 10.0
    sleeps: list[float] = []

    def monotonic() -> float:
        return now

    async def sleep(delay: float) -> None:
        nonlocal now
        sleeps.append(delay)
        now += delay

    transport = YurisakiTransport(
        client,
        _config(min_request_interval=2.0),
        wall_clock=lambda: 1_000.0,
        monotonic=monotonic,
        sleep=sleep,
    )
    transport.start()

    first = asyncio.create_task(transport.request("/a info first"))
    await _wait_for_calls(client, 1)
    await client.emit(_event())
    await first

    second = asyncio.create_task(transport.request("/a info second"))
    await _wait_for_calls(client, 2)
    assert sleeps == [2.0]
    await client.emit(_event())
    await second


def test_invalid_transport_config_is_rejected() -> None:
    with pytest.raises(ValueError, match="digits only"):
        _config(yurisaki_user_id="not-an-id")
    with pytest.raises(ValueError, match="greater than zero"):
        _config(timeout_seconds=0)
    with pytest.raises(ValueError, match="cannot be negative"):
        _config(min_request_interval=-1)
    with pytest.raises(ValueError, match="cannot be negative"):
        _config(timeout_quarantine_seconds=-1)


@pytest.mark.asyncio
async def test_request_before_start_is_rejected() -> None:
    transport = YurisakiTransport(FakeClient(), _config())

    with pytest.raises(TransportUnavailableError):
        await transport.request("/a info test")
