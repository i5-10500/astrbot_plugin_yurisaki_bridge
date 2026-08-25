"""Tests for the validated application service and safe error contract."""

from collections.abc import Sequence

import pytest

import yurisaki_bridge.service as service_module
from yurisaki_bridge.service import (
    QueryValidationError,
    YurisakiService,
    normalize_query,
)
from yurisaki_bridge.transport import (
    ResponseTimeoutError,
    SendFailedError,
    TransportShuttingDownError,
    TransportUnavailableError,
)


class FakeTransport:
    def __init__(
        self,
        response: Sequence[object] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = list(response or [])
        self.error = error
        self.commands: list[str] = []

    async def request(self, command: str) -> list[object]:
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return self.response


@pytest.mark.parametrize("query", ["", "   ", "a\n/a help", "a\tb", "x" * 121, 123])
def test_invalid_query_is_rejected(query: object) -> None:
    with pytest.raises(QueryValidationError):
        normalize_query(query)


def test_query_is_trimmed_without_changing_inner_text() -> None:
    assert normalize_query("  光（中国語版）  ") == "光（中国語版）"


@pytest.mark.asyncio
async def test_service_builds_only_the_fixed_info_command() -> None:
    transport = FakeTransport(
        [{"type": "text", "data": {"text": "曲目: Test\nBPM: 180"}}]
    )
    service = YurisakiService(transport)  # type: ignore[arg-type]

    payload = await service.song_info("  Test  ")

    assert transport.commands == ["/a info Test"]
    assert payload["ok"] is True
    assert payload["canonical_title"] == "Test"
    assert payload["bpm"] == "180"


@pytest.mark.asyncio
async def test_random_song_command_is_fixed() -> None:
    transport = FakeTransport(
        [
            {"type": "image", "data": {"url": "https://example.invalid/image"}},
            {
                "type": "text",
                "data": {"text": "曲目: Random Song\n艺术家: Test Artist"},
            },
        ]
    )
    service = YurisakiService(transport)  # type: ignore[arg-type]

    result = await service.random_song()

    assert transport.commands == ["/a rand"]
    assert result.ok is True
    assert result.canonical_title == "Random Song"
    assert result.artist == "Test Artist"


@pytest.mark.asyncio
async def test_invalid_query_never_reaches_transport() -> None:
    transport = FakeTransport()
    service = YurisakiService(transport)  # type: ignore[arg-type]

    payload = await service.song_info("first\n/a status")

    assert transport.commands == []
    assert payload["error"]["type"] == "invalid_query"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "error_type"),
    [
        (TransportUnavailableError("private detail"), "transport_unavailable"),
        (SendFailedError("private detail"), "send_failed"),
        (ResponseTimeoutError("private detail"), "timeout"),
        (TransportShuttingDownError("private detail"), "plugin_shutting_down"),
    ],
)
async def test_transport_errors_are_mapped_without_private_details(
    exception: Exception,
    error_type: str,
) -> None:
    service = YurisakiService(  # type: ignore[arg-type]
        FakeTransport(error=exception)
    )

    payload = await service.song_info("test")

    assert payload["ok"] is False
    assert payload["error"]["type"] == error_type
    assert "private detail" not in str(payload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "error_type"),
    [
        (TransportUnavailableError("private detail"), "transport_unavailable"),
        (SendFailedError("private detail"), "send_failed"),
        (ResponseTimeoutError("private detail"), "timeout"),
        (TransportShuttingDownError("private detail"), "plugin_shutting_down"),
    ],
)
async def test_random_song_transport_errors_are_safe(
    exception: Exception,
    error_type: str,
) -> None:
    service = YurisakiService(  # type: ignore[arg-type]
        FakeTransport(error=exception)
    )

    result = await service.random_song()
    payload = result.to_dict()

    assert payload["ok"] is False
    assert payload["error"]["type"] == error_type
    assert "private detail" not in str(payload)


@pytest.mark.asyncio
async def test_unexpected_parser_error_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_parser(query: str, segments: Sequence[object]) -> None:
        del query, segments
        raise RuntimeError("sensitive parser detail")

    monkeypatch.setattr(service_module, "parse_song_info_response", fail_parser)
    service = YurisakiService(  # type: ignore[arg-type]
        FakeTransport([{"type": "text", "data": {"text": "test"}}])
    )

    payload = await service.song_info("test")

    assert payload["error"]["type"] == "parse_error"
    assert "sensitive parser detail" not in str(payload)


@pytest.mark.asyncio
async def test_unexpected_random_parser_error_is_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_parser(segments: Sequence[object]) -> None:
        del segments
        raise RuntimeError("sensitive parser detail")

    monkeypatch.setattr(service_module, "parse_random_song_response", fail_parser)
    service = YurisakiService(  # type: ignore[arg-type]
        FakeTransport([{"type": "text", "data": {"text": "test"}}])
    )

    payload = (await service.random_song()).to_dict()

    assert payload["error"]["type"] == "parse_error"
    assert "sensitive parser detail" not in str(payload)
