# SPDX-FileCopyrightText: 2026 i5-10500
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Validated application service exposed to the AstrBot plugin entry point."""

import unicodedata
from dataclasses import dataclass
from typing import Any

from .models import BridgeError, RandomSongResult, SongInfoResult, SongPreviewResult
from .parser import (
    parse_preview_response,
    parse_random_song_response,
    parse_song_info_response,
)
from .transport import (
    IncompleteResponseError,
    ResponseTimeoutError,
    SendFailedError,
    TransportShuttingDownError,
    TransportUnavailableError,
    YurisakiTransport,
)

MAX_QUERY_LENGTH = 120
RANDOM_LEVEL_FILTERS = frozenset(
    {*(str(level) for level in range(1, 13)), "8+", "9+", "10+", "11+"}
)
RANDOM_CONSTANT_FILTERS = frozenset(
    {
        *(f"{constant / 10:.1f}" for constant in range(10, 80, 5)),
        *(f"{constant / 10:.1f}" for constant in range(80, 121)),
    }
)


class QueryValidationError(ValueError):
    """Raised when a query cannot safely be embedded in ``/a info``."""


class RandomFilterValidationError(ValueError):
    """Raised when a random-song filter is outside the supported whitelist."""


@dataclass(frozen=True, slots=True)
class RandomSongFilter:
    """A validated Yurisaki ``/a rand`` level or chart-constant filter."""

    filter_type: str
    value: str

    def __post_init__(self) -> None:
        allowed_values = {
            "level": RANDOM_LEVEL_FILTERS,
            "constant": RANDOM_CONSTANT_FILTERS,
        }.get(self.filter_type)
        if allowed_values is None or self.value not in allowed_values:
            raise RandomFilterValidationError("random-song filter is not supported")


class YurisakiService:
    """Build fixed supported commands and return stable, safe results."""

    def __init__(self, transport: YurisakiTransport) -> None:
        self._transport = transport

    async def song_info(self, query: object) -> dict[str, Any]:
        """Validate a title, run ``/a info``, and parse its response."""
        try:
            normalized_query = normalize_query(query)
        except QueryValidationError:
            return _error_payload(
                _safe_query(query),
                "invalid_query",
                "Query must be 1-120 characters and contain no control characters.",
            )

        try:
            segments = await self._transport.request(f"/a info {normalized_query}")
        except TransportUnavailableError:
            return _error_payload(
                normalized_query,
                "transport_unavailable",
                "Yurisaki transport is not available.",
            )
        except SendFailedError:
            return _error_payload(
                normalized_query,
                "send_failed",
                "The query could not be sent to Yurisaki.",
            )
        except ResponseTimeoutError:
            return _error_payload(
                normalized_query,
                "timeout",
                "Yurisaki did not respond before the timeout.",
            )
        except TransportShuttingDownError:
            return _error_payload(
                normalized_query,
                "plugin_shutting_down",
                "The plugin is shutting down.",
            )

        try:
            return parse_song_info_response(normalized_query, segments).to_dict()
        except Exception:
            return _error_payload(
                normalized_query,
                "parse_error",
                "The Yurisaki response could not be parsed.",
            )

    async def random_song(
        self,
        random_filter: RandomSongFilter | None = None,
    ) -> RandomSongResult:
        """Run a whitelisted ``/a rand`` variant and parse its response."""
        command = "/a rand"
        if random_filter is not None:
            command = f"{command} {random_filter.value}"
        try:
            segments = await self._transport.request(command)
        except TransportUnavailableError:
            return random_song_error(
                "transport_unavailable",
                "Yurisaki transport is not available.",
                random_filter,
            )
        except SendFailedError:
            return random_song_error(
                "send_failed",
                "The random-song query could not be sent to Yurisaki.",
                random_filter,
            )
        except ResponseTimeoutError:
            return random_song_error(
                "timeout",
                "Yurisaki did not respond before the timeout.",
                random_filter,
            )
        except TransportShuttingDownError:
            return random_song_error(
                "plugin_shutting_down",
                "The plugin is shutting down.",
                random_filter,
            )

        try:
            result = parse_random_song_response(segments)
            _set_random_filter(result, random_filter)
            return result
        except Exception:
            return random_song_error(
                "parse_error",
                "The Yurisaki random-song response could not be parsed.",
                random_filter,
            )

    async def song_preview(self, query: object) -> SongPreviewResult:
        """Validate a title, run ``/a preview``, and parse both response events."""
        try:
            normalized_query = normalize_query(query)
        except QueryValidationError:
            return preview_error(
                _safe_query(query),
                "invalid_query",
                "Query must be 1-120 characters and contain no control characters.",
            )

        try:
            events = await self._transport.request_preview(
                f"/a preview {normalized_query}"
            )
        except TransportUnavailableError:
            return preview_error(
                normalized_query,
                "transport_unavailable",
                "Yurisaki transport is not available.",
            )
        except SendFailedError:
            return preview_error(
                normalized_query,
                "send_failed",
                "The preview query could not be sent to Yurisaki.",
            )
        except IncompleteResponseError:
            return preview_error(
                normalized_query,
                "incomplete_response",
                "Yurisaki did not return both preview text and audio in time.",
            )
        except ResponseTimeoutError:
            return preview_error(
                normalized_query,
                "timeout",
                "Yurisaki did not respond before the timeout.",
            )
        except TransportShuttingDownError:
            return preview_error(
                normalized_query,
                "plugin_shutting_down",
                "The plugin is shutting down.",
            )

        try:
            return parse_preview_response(normalized_query, events)
        except Exception:
            return preview_error(
                normalized_query,
                "parse_error",
                "The Yurisaki preview response could not be parsed.",
            )


def normalize_query(query: object) -> str:
    """Return a bounded single-line query suitable for a fixed command."""
    if not isinstance(query, str):
        raise QueryValidationError("query must be a string")
    normalized = query.strip()
    if not normalized or len(normalized) > MAX_QUERY_LENGTH:
        raise QueryValidationError("query length is invalid")
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise QueryValidationError("query contains a control character")
    return normalized


def normalize_random_filter(value: object) -> RandomSongFilter | None:
    """Validate an optional exact level or chart-constant filter."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise RandomFilterValidationError("random-song filter must be a string")

    normalized = value.strip()
    if not normalized:
        return None
    if normalized in RANDOM_LEVEL_FILTERS:
        return RandomSongFilter(filter_type="level", value=normalized)
    if normalized in RANDOM_CONSTANT_FILTERS:
        return RandomSongFilter(filter_type="constant", value=normalized)
    raise RandomFilterValidationError("random-song filter is not supported")


def unavailable_payload(query: object, message: str) -> dict[str, Any]:
    """Build an unavailable result before the service can be constructed."""
    return _error_payload(_safe_query(query), "transport_unavailable", message)


def preview_unavailable_result(query: object, message: str) -> SongPreviewResult:
    """Build an unavailable preview result before service construction."""
    return preview_error(_safe_query(query), "transport_unavailable", message)


def random_song_error(
    error_type: str,
    message: str,
    random_filter: RandomSongFilter | None = None,
) -> RandomSongResult:
    """Build a safe random-song failure result."""
    result = RandomSongResult(
        raw_text="",
        ok=False,
        error=BridgeError(error_type=error_type, message=message),
    )
    _set_random_filter(result, random_filter)
    return result


def preview_error(query: str, error_type: str, message: str) -> SongPreviewResult:
    """Build a safe preview failure result."""
    return SongPreviewResult(
        query=query,
        raw_text="",
        ok=False,
        error=BridgeError(error_type=error_type, message=message),
    )


def _set_random_filter(
    result: RandomSongResult,
    random_filter: RandomSongFilter | None,
) -> None:
    if random_filter is None:
        return
    result.filter_type = random_filter.filter_type
    result.filter_value = random_filter.value


def _safe_query(query: object) -> str:
    if not isinstance(query, str):
        return ""
    return query.strip()[:MAX_QUERY_LENGTH]


def _error_payload(query: str, error_type: str, message: str) -> dict[str, Any]:
    return SongInfoResult(
        query=query,
        raw_text="",
        ok=False,
        error=BridgeError(error_type=error_type, message=message),
    ).to_dict()
