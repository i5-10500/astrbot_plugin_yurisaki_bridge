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
PLUGIN_PACKAGE = "astrbot_plugin_yurisaki_bridge"
BOT_ID = "100001"
YURISAKI_ID = "200002"


class FakeLogger:
    def __init__(self) -> None:
        self.records: list[str] = []

    def info(self, *args: object, **kwargs: object) -> None:
        del kwargs
        self.records.append(_format_log_args(args))

    def warning(self, *args: object, **kwargs: object) -> None:
        del kwargs
        self.records.append(_format_log_args(args))


def _format_log_args(args: tuple[object, ...]) -> str:
    if not args:
        return ""
    message = str(args[0])
    return message % args[1:] if len(args) > 1 else message


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


class FakeRecord:
    def __init__(self, *, file: str, url: str) -> None:
        self.file = file
        self.url = url


@pytest.fixture
def plugin_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    astrbot = ModuleType("astrbot")
    api = ModuleType("astrbot.api")
    event_api = ModuleType("astrbot.api.event")
    components_api = ModuleType("astrbot.api.message_components")
    star_api = ModuleType("astrbot.api.star")
    api.AstrBotConfig = dict  # type: ignore[attr-defined]
    api.logger = FakeLogger()  # type: ignore[attr-defined]
    event_api.AstrMessageEvent = object  # type: ignore[attr-defined]
    event_api.filter = FakeFilter  # type: ignore[attr-defined]
    components_api.Record = FakeRecord  # type: ignore[attr-defined]
    star_api.Context = object  # type: ignore[attr-defined]
    star_api.Star = FakeStar  # type: ignore[attr-defined]
    astrbot.api = api  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "astrbot", astrbot)
    monkeypatch.setitem(sys.modules, "astrbot.api", api)
    monkeypatch.setitem(sys.modules, "astrbot.api.event", event_api)
    monkeypatch.setitem(sys.modules, "astrbot.api.message_components", components_api)
    monkeypatch.setitem(sys.modules, "astrbot.api.star", star_api)

    # AstrBot imports an installed plugin as a package below data.plugins. Ensure
    # the entry point resolves its own modules through that package instead of
    # relying on the repository root being present on sys.path.
    plugin_package = ModuleType(PLUGIN_PACKAGE)
    plugin_package.__path__ = [str(ROOT)]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, PLUGIN_PACKAGE, plugin_package)
    monkeypatch.setitem(sys.modules, "yurisaki_bridge", None)

    spec = importlib.util.spec_from_file_location(
        f"{PLUGIN_PACKAGE}.main", ROOT / "main.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
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
        self.sent_results: list[object] = []
        self.extras: dict[str, object] = {}

    def stop_event(self) -> None:
        self.stopped = True

    def image_result(self, source: str) -> dict[str, str]:
        return {"image": source}

    def chain_result(self, chain: list[object]) -> dict[str, list[object]]:
        return {"chain": chain}

    async def send(self, result: object) -> None:
        self.sent_results.append(result)

    def get_extra(self, key: str) -> object | None:
        return self.extras.get(key)

    def set_extra(self, key: str, value: object) -> None:
        self.extras[key] = value


class FailingSendEvent(FakeEvent):
    async def send(self, result: object) -> None:
        raise RuntimeError(f"sensitive delivery detail: {result}")


def _raw_response() -> dict[str, object]:
    return {
        "post_type": "message",
        "message_type": "private",
        "user_id": int(YURISAKI_ID),
        "self_id": int(BOT_ID),
        "time": int(time.time()),
        "message_id": 123,
        "message": [{"type": "text", "data": {"text": "曲目: Test\nBPM: 180"}}],
    }


def _raw_rand_response() -> dict[str, object]:
    response = _raw_response()
    response["message_id"] = 456
    response["message"] = [
        {
            "type": "image",
            "data": {
                "file": "private-file",
                "url": "https://example.invalid/random.jpg",
            },
        },
        {
            "type": "text",
            "data": {
                "text": (
                    "为您推荐的曲目是：\n曲目：Random Song\n"
                    "艺术家：Test Artist\nBPM：180"
                )
            },
        },
    ]
    return response


def _raw_preview_text() -> dict[str, object]:
    response = _raw_response()
    response["message_id"] = 700
    response["message"] = [{"type": "text", "data": {"text": "曲目：Synthesis."}}]
    return response


def _raw_preview_record() -> dict[str, object]:
    response = _raw_response()
    response["message_id"] = 701
    response["message"] = [
        {
            "type": "record",
            "data": {
                "file": "private-audio-id",
                "path": "C:/private/cache.wav",
                "url": "https://example.invalid/preview.wav?token=private",
            },
        }
    ]
    return response


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
async def test_random_song_tool_sends_image_to_original_event(
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
    caller_event = FakeEvent({})
    other_event = FakeEvent({})

    task = asyncio.create_task(plugin.yurisaki_random_song(caller_event, ""))
    await asyncio.wait_for(client.sent.wait(), timeout=0.2)
    raw_response = _raw_rand_response()
    await client.emit(raw_response)
    intercept_event = FakeEvent(raw_response)
    await plugin.intercept_yurisaki_response(intercept_event)
    serialized = await task
    payload = json.loads(serialized)

    assert client.calls[1] == (
        "send_private_msg",
        {"user_id": int(YURISAKI_ID), "message": "/a rand"},
    )
    assert caller_event.sent_results == [
        {"image": "https://example.invalid/random.jpg"}
    ]
    assert other_event.sent_results == []
    assert payload["ok"] is True
    assert payload["canonical_title"] == "Random Song"
    assert payload["image_count"] == 1
    assert payload["image_delivered"] is True
    assert "https://example.invalid/random.jpg" not in serialized
    assert "private-file" not in serialized
    assert intercept_event.stopped is True

    duplicate = json.loads(await plugin.yurisaki_random_song(caller_event, ""))
    assert duplicate["error"]["type"] == "duplicate_tool_call"
    assert len(client.calls) == 2
    assert len(caller_event.sent_results) == 1

    await plugin.terminate()


@pytest.mark.asyncio
async def test_random_song_tool_sends_whitelisted_filter(
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
    caller_event = FakeEvent({})

    task = asyncio.create_task(plugin.yurisaki_random_song(caller_event, "10.7"))
    await asyncio.wait_for(client.sent.wait(), timeout=0.2)
    await client.emit(_raw_rand_response())
    payload = json.loads(await task)

    assert client.calls[1] == (
        "send_private_msg",
        {"user_id": int(YURISAKI_ID), "message": "/a rand 10.7"},
    )
    assert payload["filter"] == {"type": "constant", "value": "10.7"}
    assert payload["image_delivered"] is True

    await plugin.terminate()


@pytest.mark.asyncio
async def test_invalid_random_song_filter_never_reaches_transport_or_guard(
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
    caller_event = FakeEvent({})

    invalid = json.loads(await plugin.yurisaki_random_song(caller_event, "10.70"))

    assert invalid["error"]["type"] == "invalid_filter"
    assert len(client.calls) == 1
    assert caller_event.extras == {}

    task = asyncio.create_task(plugin.yurisaki_random_song(caller_event, "8+"))
    await asyncio.wait_for(client.sent.wait(), timeout=0.2)
    await client.emit(_raw_rand_response())
    valid = json.loads(await task)

    assert client.calls[1][1]["message"] == "/a rand 8+"
    assert valid["ok"] is True

    await plugin.terminate()


@pytest.mark.asyncio
async def test_random_song_missing_image_is_not_sent(
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
    caller_event = FakeEvent({})

    task = asyncio.create_task(plugin.yurisaki_random_song(caller_event))
    await asyncio.wait_for(client.sent.wait(), timeout=0.2)
    await client.emit(_raw_response())
    payload = json.loads(await task)

    assert payload["ok"] is False
    assert payload["error"]["type"] == "incomplete_response"
    assert caller_event.sent_results == []

    await plugin.terminate()


@pytest.mark.asyncio
async def test_random_song_image_delivery_failure_is_safe(
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
    caller_event = FailingSendEvent({})

    task = asyncio.create_task(plugin.yurisaki_random_song(caller_event))
    await asyncio.wait_for(client.sent.wait(), timeout=0.2)
    await client.emit(_raw_rand_response())
    serialized = await task
    payload = json.loads(serialized)
    records = "\n".join(plugin_module.logger.records)  # type: ignore[attr-defined]

    assert payload["ok"] is True
    assert payload["image_delivered"] is False
    assert "example.invalid" not in serialized
    assert "example.invalid" not in records
    assert "private-file" not in records

    await plugin.terminate()


@pytest.mark.asyncio
async def test_preview_tool_sends_audio_only_to_original_event(
    plugin_module: ModuleType,
) -> None:
    client = FakeClient()
    plugin = plugin_module.YurisakiBridgePlugin(  # type: ignore[attr-defined]
        FakeContext([FakePlatform(client)]),
        {
            "enabled": True,
            "enable_preview_tool": True,
            "yurisaki_user_id": YURISAKI_ID,
            "timeout_seconds": 0.2,
            "min_request_interval": 0.0,
        },
    )
    await plugin.initialize()
    caller_event = FakeEvent({})
    other_event = FakeEvent({})

    task = asyncio.create_task(
        plugin.yurisaki_song_preview(caller_event, " synthesis ")
    )
    await asyncio.wait_for(client.sent.wait(), timeout=0.2)
    text_response = _raw_preview_text()
    record_response = _raw_preview_record()
    await client.emit(text_response)
    assert task.done() is False
    await client.emit(record_response)

    text_intercept = FakeEvent(text_response)
    record_intercept = FakeEvent(record_response)
    await plugin.intercept_yurisaki_response(text_intercept)
    await plugin.intercept_yurisaki_response(record_intercept)
    serialized = await task
    payload = json.loads(serialized)

    assert client.calls[1][1]["message"] == "/a preview synthesis"
    assert payload["ok"] is True
    assert payload["canonical_title"] == "Synthesis."
    assert payload["audio_count"] == 1
    assert payload["audio_delivered"] is True
    assert len(caller_event.sent_results) == 1
    record = caller_event.sent_results[0]["chain"][0]  # type: ignore[index]
    assert isinstance(record, FakeRecord)
    assert record.url.startswith("https://example.invalid/preview.wav")
    assert other_event.sent_results == []
    assert "example.invalid" not in serialized
    assert "private-audio-id" not in serialized
    assert text_intercept.stopped is True
    assert record_intercept.stopped is True

    duplicate = json.loads(await plugin.yurisaki_song_preview(caller_event, "test"))
    assert duplicate["error"]["type"] == "duplicate_tool_call"
    assert len(client.calls) == 2
    assert len(caller_event.sent_results) == 1

    await plugin.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "preview_config",
    [{}, {"enable_preview_tool": False}],
)
async def test_preview_invalid_or_disabled_never_reaches_transport(
    plugin_module: ModuleType,
    preview_config: dict[str, object],
) -> None:
    client = FakeClient()
    plugin = plugin_module.YurisakiBridgePlugin(  # type: ignore[attr-defined]
        FakeContext([FakePlatform(client)]),
        {
            "enabled": True,
            "yurisaki_user_id": YURISAKI_ID,
            **preview_config,
        },
    )
    await plugin.initialize()
    caller_event = FakeEvent({})

    invalid = json.loads(
        await plugin.yurisaki_song_preview(caller_event, "first\n/a help")
    )
    disabled = json.loads(await plugin.yurisaki_song_preview(caller_event, "test"))

    assert invalid["error"]["type"] == "invalid_query"
    assert disabled["error"]["type"] == "preview_disabled"
    assert len(client.calls) == 1
    assert caller_event.extras == {}

    await plugin.terminate()


@pytest.mark.asyncio
async def test_preview_audio_delivery_failure_is_safe(
    plugin_module: ModuleType,
) -> None:
    client = FakeClient()
    plugin = plugin_module.YurisakiBridgePlugin(  # type: ignore[attr-defined]
        FakeContext([FakePlatform(client)]),
        {
            "enabled": True,
            "enable_preview_tool": True,
            "yurisaki_user_id": YURISAKI_ID,
            "timeout_seconds": 0.2,
            "min_request_interval": 0.0,
        },
    )
    await plugin.initialize()
    caller_event = FailingSendEvent({})

    task = asyncio.create_task(plugin.yurisaki_song_preview(caller_event, "test"))
    await asyncio.wait_for(client.sent.wait(), timeout=0.2)
    await client.emit(_raw_preview_text())
    await client.emit(_raw_preview_record())
    serialized = await task
    payload = json.loads(serialized)
    records = "\n".join(plugin_module.logger.records)  # type: ignore[attr-defined]

    assert payload["ok"] is True
    assert payload["audio_delivered"] is False
    assert "example.invalid" not in serialized
    assert "example.invalid" not in records
    assert "private-audio-id" not in records

    await plugin.terminate()


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


@pytest.mark.asyncio
async def test_debug_logging_does_not_include_bot_account(
    plugin_module: ModuleType,
) -> None:
    client = FakeClient()
    plugin = plugin_module.YurisakiBridgePlugin(  # type: ignore[attr-defined]
        FakeContext([FakePlatform(client)]),
        {"enabled": True, "debug_logging": True},
    )

    await plugin.initialize()

    records = "\n".join(plugin_module.logger.records)  # type: ignore[attr-defined]
    assert "qq-main" in records
    assert BOT_ID not in records

    await plugin.terminate()


def test_login_info_requires_numeric_user_id(plugin_module: ModuleType) -> None:
    with pytest.raises(RuntimeError, match="valid user_id"):
        plugin_module._login_user_id({"user_id": "not-numeric"})  # type: ignore[attr-defined]


def test_random_image_url_requires_http_or_https(plugin_module: ModuleType) -> None:
    safe_image_url = plugin_module._safe_image_url  # type: ignore[attr-defined]

    assert safe_image_url("https://example.invalid/image.jpg") is not None
    assert safe_image_url("http://example.invalid/image.jpg") is not None
    assert safe_image_url("file:///private/path.jpg") is None
    assert safe_image_url("javascript:alert(1)") is None
    assert safe_image_url("not-a-url") is None

    safe_media_url = plugin_module._safe_media_url  # type: ignore[attr-defined]
    assert safe_media_url("https://example.invalid/audio.wav") is not None
    assert safe_media_url("file:///private/audio.wav") is None
