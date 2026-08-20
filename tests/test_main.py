"""Offline contract tests for the AstrBot-facing plugin entry point."""

import asyncio
import importlib.util
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOT_ID = "100001"
YURISAKI_ID = "200002"


class FakeLogger:
    def info(self, *args: object, **kwargs: object) -> None:
        pass

    def warning(self, *args: object, **kwargs: object) -> None:
        pass


class FakeFilter:
    PlatformAdapterType = SimpleNamespace(AIOCQHTTP=1)
    EventMessageType = SimpleNamespace(PRIVATE_MESSAGE=1)

    @staticmethod
    def _decorator(*args: object, **kwargs: object) -> Callable[[object], object]:
        del args, kwargs

        def decorate(function: object) -> object:
            return function

        return decorate

    llm_tool = _decorator
    platform_adapter_type = _decorator
    event_message_type = _decorator


class FakeStar:
    def __init__(self, context: object) -> None:
        self.context = context


@pytest.fixture
def plugin_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    astrbot = ModuleType("astrbot")
    api = ModuleType("astrbot.api")
    event_api = ModuleType("astrbot.api.event")
    star_api = ModuleType("astrbot.api.star")
    api.AstrBotConfig = dict  # type: ignore[attr-defined]
    api.logger = FakeLogger()  # type: ignore[attr-defined]
    event_api.AstrMessageEvent = object  # type: ignore[attr-defined]
    event_api.filter = FakeFilter  # type: ignore[attr-defined]
    star_api.Context = object  # type: ignore[attr-defined]
    star_api.Star = FakeStar  # type: ignore[attr-defined]
    astrbot.api = api  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "astrbot", astrbot)
    monkeypatch.setitem(sys.modules, "astrbot.api", api)
    monkeypatch.setitem(sys.modules, "astrbot.api.event", event_api)
    monkeypatch.setitem(sys.modules, "astrbot.api.star", star_api)

    spec = importlib.util.spec_from_file_location(
        "tested_plugin_main", ROOT / "main.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeClient:
    def __init__(self) -> None:
        self.handlers: list[Callable[..., object]] = []
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.sent = asyncio.Event()

    def subscribe(self, event_name: str, handler: Callable[..., object]) -> None:
        assert event_name == "message.private"
        self.handlers.append(handler)

    def unsubscribe(self, event_name: str, handler: Callable[..., object]) -> None:
        assert event_name == "message.private"
        self.handlers.remove(handler)

    async def call_action(self, action: str, **params: object) -> Any:
        self.calls.append((action, params))
        if action == "get_login_info":
            return {"user_id": int(BOT_ID), "nickname": "bridge"}
        self.sent.set()
        return {"message_id": 1}

    async def emit(self, event: object) -> None:
        for handler in list(self.handlers):
            await handler(event)


class SlowLoginClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.login_started = asyncio.Event()
        self.release_login = asyncio.Event()

    async def call_action(self, action: str, **params: object) -> Any:
        if action != "get_login_info":
            return await super().call_action(action, **params)
        self.calls.append((action, params))
        self.login_started.set()
        await self.release_login.wait()
        return {"user_id": int(BOT_ID)}


class FakePlatform:
    def __init__(self, client: FakeClient, platform_id: str = "qq-main") -> None:
        self._client = client
        self._metadata = SimpleNamespace(name="aiocqhttp", id=platform_id)

    def get_client(self) -> FakeClient:
        return self._client

    def meta(self) -> SimpleNamespace:
        return self._metadata


class FakeContext:
    def __init__(self, platforms: list[FakePlatform]) -> None:
        self.platform_manager = SimpleNamespace(get_insts=lambda: platforms)


class FakeEvent:
    def __init__(self, raw_message: object) -> None:
        self.message_obj = SimpleNamespace(raw_message=raw_message)
        self.stopped = False

    def stop_event(self) -> None:
        self.stopped = True


def _raw_response() -> dict[str, object]:
    return {
        "post_type": "message",
        "message_type": "private",
        "user_id": int(YURISAKI_ID),
        "self_id": int(BOT_ID),
        "time": int(time.time()),
        "message_id": 123,
        "message": [{"type": "text", "data": {"text": "曲目: Test"}}],
    }


@pytest.mark.asyncio
async def test_tool_runs_fixed_command_and_intercepts_response(
    plugin_module: ModuleType,
) -> None:
    client = FakeClient()
    plugin = plugin_module.YurisakiBridgePlugin(  # type: ignore[attr-defined]
        FakeContext([FakePlatform(client)]),
        {
            "enabled": True,
            "yurisaki_user_id": YURISAKI_ID,
            "timeout_seconds": 0.2,
            "min_request_interval": 0.0,
        },
    )
    await plugin.initialize()

    task = asyncio.create_task(plugin.yurisaki_song_info(FakeEvent({}), " Test "))
    await asyncio.wait_for(client.sent.wait(), timeout=0.2)
    raw_response = _raw_response()
    await client.emit(raw_response)
    intercept_event = FakeEvent(raw_response)
    await plugin.intercept_yurisaki_response(intercept_event)
    payload = json.loads(await task)

    assert client.calls[0] == ("get_login_info", {})
    assert client.calls[1] == (
        "send_private_msg",
        {"user_id": int(YURISAKI_ID), "message": "/a info Test"},
    )
    assert payload["ok"] is True
    assert payload["canonical_title"] == "Test"
    assert intercept_event.stopped is True

    await plugin.terminate()
    assert client.handlers == []


@pytest.mark.asyncio
async def test_tool_returns_safe_error_when_platform_is_unavailable(
    plugin_module: ModuleType,
) -> None:
    plugin = plugin_module.YurisakiBridgePlugin(  # type: ignore[attr-defined]
        FakeContext([]),
        {"enabled": True},
    )

    await plugin.initialize()
    payload = json.loads(await plugin.yurisaki_song_info(FakeEvent({}), "Test"))

    assert payload["ok"] is False
    assert payload["error"]["type"] == "transport_unavailable"


@pytest.mark.asyncio
async def test_disabled_plugin_does_not_touch_platform(
    plugin_module: ModuleType,
) -> None:
    client = FakeClient()
    plugin = plugin_module.YurisakiBridgePlugin(  # type: ignore[attr-defined]
        FakeContext([FakePlatform(client)]),
        {"enabled": False},
    )

    await plugin.initialize()
    payload = json.loads(await plugin.yurisaki_song_info(FakeEvent({}), "Test"))

    assert client.calls == []
    assert payload["error"]["type"] == "transport_unavailable"


@pytest.mark.asyncio
async def test_terminate_during_setup_cannot_leave_a_raw_callback(
    plugin_module: ModuleType,
) -> None:
    client = SlowLoginClient()
    plugin = plugin_module.YurisakiBridgePlugin(  # type: ignore[attr-defined]
        FakeContext([FakePlatform(client)]),
        {"enabled": True},
    )
    initialize_task = asyncio.create_task(plugin.initialize())
    await asyncio.wait_for(client.login_started.wait(), timeout=0.2)

    await plugin.terminate()
    client.release_login.set()
    await initialize_task

    assert client.handlers == []
    assert plugin._transport is None


def test_login_info_requires_numeric_user_id(plugin_module: ModuleType) -> None:
    with pytest.raises(RuntimeError, match="valid user_id"):
        plugin_module._login_user_id({"user_id": "not-numeric"})  # type: ignore[attr-defined]
