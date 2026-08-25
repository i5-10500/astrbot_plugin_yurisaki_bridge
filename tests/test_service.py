"""Tests for the validated application service and safe error contract."""

from collections.abc import Sequence

import pytest

import yurisaki_bridge.service as service_module
from yurisaki_bridge.service import (
    QueryValidationError,
    RandomFilterValidationError,
    RandomSongFilter,
    YurisakiService,
    normalize_query,
    normalize_random_filter,
)
from yurisaki_bridge.transport import (
    IncompleteResponseError,
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
        preview_response: Sequence[Sequence[object]] | None = None,
    ) -> None:
        self.response = list(response or [])
        self.error = error
        self.preview_response = [list(event) for event in (preview_response or [])]
        self.commands: list[str] = []

    async def request(self, command: str) -> list[object]:
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return self.response

    async def request_preview(self, command: str) -> list[list[object]]:
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return self.preview_response


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


@pytest.mark.parametrize(
    ("value", "filter_type"),
    [
        ("1", "level"),
        ("8+", "level"),
        ("12", "level"),
        ("1.0", "constant"),
        ("7.5", "constant"),
        ("8.0", "constant"),
        ("10.7", "constant"),
        ("12.0", "constant"),
    ],
)
def test_random_song_filter_whitelist(value: str, filter_type: str) -> None:
    random_filter = normalize_random_filter(f"  {value}  ")

    assert random_filter is not None
    assert random_filter.value == value
    assert random_filter.filter_type == filter_type


@pytest.mark.parametrize(
    "value",
    ["0", "7+", "12+", "1.1", "7.6", "8.01", "12.1", "10.70", "/a info", 10.7],
)
def test_invalid_random_song_filter_is_rejected(value: object) -> None:
    with pytest.raises(RandomFilterValidationError):
        normalize_random_filter(value)


@pytest.mark.parametrize(
    ("filter_type", "value"),
    [("level", "10.7"), ("constant", "10+"), ("unknown", "10")],
)
def test_random_song_filter_type_cannot_bypass_whitelist(
    filter_type: str,
    value: str,
) -> None:
    with pytest.raises(RandomFilterValidationError):
        RandomSongFilter(filter_type=filter_type, value=value)


@pytest.mark.parametrize("value", ["", "   ", None])
def test_empty_random_song_filter_means_unfiltered(value: object) -> None:
    assert normalize_random_filter(value) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("value", "expected_type"),
    [("8+", "level"), ("10.7", "constant")],
)
async def test_random_song_builds_only_whitelisted_filtered_command(
    value: str,
    expected_type: str,
) -> None:
    transport = FakeTransport(
        [
            {"type": "image", "data": {"url": "https://example.invalid/image"}},
            {
                "type": "text",
                "data": {"text": "曲目: Random Song [FTR]\n难度: 10.7"},
            },
        ]
    )
    service = YurisakiService(transport)  # type: ignore[arg-type]

    result = await service.random_song(normalize_random_filter(value))
    payload = result.to_dict()

    assert transport.commands == [f"/a rand {value}"]
    assert payload["filter"] == {"type": expected_type, "value": value}
    assert payload["canonical_title"] == "Random Song [FTR]"
    assert payload["difficulties"] == ["10.7"]


@pytest.mark.asyncio
async def test_random_song_preserves_filter_on_known_upstream_error() -> None:
    transport = FakeTransport(
        [{"type": "text", "data": {"text": "没有找到符合条件的曲目。"}}]
    )
    service = YurisakiService(transport)  # type: ignore[arg-type]

    payload = (await service.random_song(normalize_random_filter("11+"))).to_dict()

    assert payload["ok"] is False
    assert payload["filter"] == {"type": "level", "value": "11+"}
    assert payload["error"]["type"] == "no_matching_song"
    assert payload["image_count"] == 0


@pytest.mark.asyncio
async def test_preview_command_is_fixed_and_query_is_validated() -> None:
    transport = FakeTransport(
        preview_response=[
            [{"type": "text", "data": {"text": "曲目：Synthesis."}}],
            [
                {
                    "type": "record",
                    "data": {"url": "https://example.invalid/preview.wav"},
                }
            ],
        ]
    )
    service = YurisakiService(transport)  # type: ignore[arg-type]

    result = await service.song_preview("  synthesis  ")

    assert transport.commands == ["/a preview synthesis"]
    assert result.ok is True
    assert result.canonical_title == "Synthesis."

    invalid = await service.song_preview("first\n/a help")
    assert invalid.error is not None
    assert invalid.error.error_type == "invalid_query"
    assert transport.commands == ["/a preview synthesis"]


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
@pytest.mark.parametrize(
    ("exception", "error_type"),
    [
        (TransportUnavailableError("private detail"), "transport_unavailable"),
        (SendFailedError("private detail"), "send_failed"),
        (ResponseTimeoutError("private detail"), "timeout"),
        (IncompleteResponseError("private detail"), "incomplete_response"),
        (TransportShuttingDownError("private detail"), "plugin_shutting_down"),
    ],
)
async def test_preview_transport_errors_are_safe(
    exception: Exception,
    error_type: str,
) -> None:
    service = YurisakiService(  # type: ignore[arg-type]
        FakeTransport(error=exception)
    )

    payload = (await service.song_preview("test")).to_dict()

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
