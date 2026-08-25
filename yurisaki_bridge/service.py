# SPDX-FileCopyrightText: 2026 i5-10500
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Validated application service exposed to the AstrBot plugin entry point."""

import unicodedata
from typing import Any

from .models import BridgeError, RandomSongResult, SongInfoResult
from .parser import parse_random_song_response, parse_song_info_response
from .transport import (
    ResponseTimeoutError,
    SendFailedError,
    TransportShuttingDownError,
    TransportUnavailableError,
    YurisakiTransport,
)

MAX_QUERY_LENGTH = 120


class QueryValidationError(ValueError):
    """Raised when a query cannot safely be embedded in ``/a info``."""


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

    async def random_song(self) -> RandomSongResult:
        """Run only ``/a rand`` and parse its proven single-event response."""
        try:
            segments = await self._transport.request("/a rand")
        except TransportUnavailableError:
            return random_song_error(
                "transport_unavailable",
                "Yurisaki transport is not available.",
            )
        except SendFailedError:
            return random_song_error(
                "send_failed",
                "The random-song query could not be sent to Yurisaki.",
            )
        except ResponseTimeoutError:
            return random_song_error(
                "timeout",
                "Yurisaki did not respond before the timeout.",
            )
        except TransportShuttingDownError:
            return random_song_error(
                "plugin_shutting_down",
                "The plugin is shutting down.",
            )

        try:
            return parse_random_song_response(segments)
        except Exception:
            return random_song_error(
                "parse_error",
                "The Yurisaki random-song response could not be parsed.",
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


def unavailable_payload(query: object, message: str) -> dict[str, Any]:
    """Build an unavailable result before the service can be constructed."""
    return _error_payload(_safe_query(query), "transport_unavailable", message)


def random_song_error(error_type: str, message: str) -> RandomSongResult:
    """Build a safe random-song failure result."""
    return RandomSongResult(
        raw_text="",
        ok=False,
        error=BridgeError(error_type=error_type, message=message),
    )


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
