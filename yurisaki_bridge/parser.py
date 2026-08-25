# SPDX-FileCopyrightText: 2026 i5-10500
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Convert OneBot message segments into stable bridge results."""

import re
from collections.abc import Mapping, Sequence

from .models import BridgeError, ImageReference, RandomSongResult, SongInfoResult

_FIELD_LINE = re.compile(
    r"^\s*(?:[-•·]\s*)?(?P<label>[^:：\r\n]{1,32})\s*[:：]\s*(?P<value>.*)\s*$"
)
_LIST_SEPARATOR = re.compile(r"\s*(?:/|／|\||,|，)\s*")

_FIELD_ALIASES = {
    "曲目": "canonical_title",
    "曲名": "canonical_title",
    "曲目id": "song_id",
    "歌曲id": "song_id",
    "难度": "difficulties",
    "物量": "note_counts",
    "谱面设计": "charters",
    "谱师": "charters",
    "曲侧": "side",
    "曲师": "artist",
    "作曲": "artist",
    "艺术家": "artist",
    "bpm": "bpm",
    "版本": "version",
    "上线日期": "release_date",
    "发布日期": "release_date",
    "实装日期": "release_date",
    "曲包": "pack",
}
_LIST_FIELDS = {"difficulties", "note_counts", "charters"}
_IDENTITY_FIELDS = {"canonical_title", "song_id"}
_RAND_PREAMBLE_LABELS = {"为您推荐的曲目是"}
_RAND_ERROR_MESSAGES = {
    "谱面定数应该在 [1.0, 12.0] 区间内。": (
        "invalid_filter",
        "The requested chart constant is outside Yurisaki's supported range.",
    ),
    "没有找到符合条件的曲目。": (
        "no_matching_song",
        "Yurisaki found no song matching the requested filter.",
    ),
}


def extract_message_content(
    segments: Sequence[object],
) -> tuple[str, list[ImageReference]]:
    """Extract text and bounded image metadata from OneBot v11 segments."""
    text_parts: list[str] = []
    images: list[ImageReference] = []

    for segment in segments:
        if not isinstance(segment, Mapping):
            continue
        segment_type = segment.get("type")
        raw_data = segment.get("data")
        data = raw_data if isinstance(raw_data, Mapping) else segment

        if segment_type == "text":
            text = data.get("text")
            if isinstance(text, str):
                text_parts.append(text)
        elif segment_type == "image":
            file = _optional_string(data.get("file"))
            url = _optional_string(data.get("url"))
            if file is not None or url is not None:
                images.append(ImageReference(file=file, url=url))

    return "".join(text_parts), images


def parse_song_info_response(
    query: str,
    segments: Sequence[object],
) -> SongInfoResult:
    """Parse a Yurisaki ``/a info`` response without assuming field order."""
    raw_text, images = extract_message_content(segments)
    result = SongInfoResult(query=query, raw_text=raw_text, images=images)

    if not raw_text.strip():
        result.ok = False
        result.error = BridgeError(
            error_type="invalid_response",
            message="Yurisaki response contained no text.",
        )
        return result

    parsed_fields = _parse_fields(raw_text, result.extra_fields)
    _apply_fields(result, parsed_fields)

    if not _has_song_info_shape(parsed_fields):
        result.ok = False
        result.error = BridgeError(
            error_type="invalid_response",
            message="Yurisaki response did not match the expected song info format.",
        )

    return result


def parse_random_song_response(segments: Sequence[object]) -> RandomSongResult:
    """Parse the single-event image-then-text response observed for ``/a rand``."""
    raw_text, images = extract_message_content(segments)
    result = RandomSongResult(raw_text=raw_text, images=images)

    if not raw_text.strip():
        result.ok = False
        result.error = BridgeError(
            error_type="invalid_response",
            message="Yurisaki random-song response contained no text.",
        )
        return result

    upstream_error = _RAND_ERROR_MESSAGES.get(raw_text.strip())
    if upstream_error is not None:
        error_type, message = upstream_error
        result.ok = False
        result.error = BridgeError(error_type=error_type, message=message)
        return result

    parsed_fields = _parse_fields(
        raw_text,
        result.extra_fields,
        ignored_labels=_RAND_PREAMBLE_LABELS,
    )
    _apply_fields(result, parsed_fields)

    if not _has_song_info_shape(parsed_fields):
        result.ok = False
        result.error = BridgeError(
            error_type="invalid_response",
            message="Yurisaki random-song response had an invalid text shape.",
        )
    elif not images:
        result.ok = False
        result.error = BridgeError(
            error_type="incomplete_response",
            message="Yurisaki random-song response contained no image.",
        )

    return result


def _parse_fields(
    raw_text: str,
    extra_fields: dict[str, str],
    *,
    ignored_labels: set[str] | None = None,
) -> dict[str, str | list[str]]:
    parsed_fields: dict[str, str | list[str]] = {}
    for line in raw_text.splitlines():
        match = _FIELD_LINE.match(line)
        if match is None:
            continue

        label = match.group("label").strip()
        value = match.group("value").strip()
        normalized_label = _normalize_label(label)
        if ignored_labels is not None and normalized_label in ignored_labels:
            continue
        field_name = _FIELD_ALIASES.get(normalized_label)
        if field_name is None:
            _store_extra_field(extra_fields, label, value)
        elif field_name in _LIST_FIELDS:
            parsed_fields[field_name] = _split_list(value)
        else:
            parsed_fields[field_name] = value
    return parsed_fields


def _apply_fields(
    result: SongInfoResult | RandomSongResult,
    parsed_fields: Mapping[str, str | list[str]],
) -> None:
    for field_name, value in parsed_fields.items():
        setattr(result, field_name, value)


def _normalize_label(label: str) -> str:
    return re.sub(r"\s+", "", label).casefold()


def _split_list(value: str) -> list[str]:
    if not value:
        return []
    return [item for item in _LIST_SEPARATOR.split(value) if item]


def _has_song_info_shape(fields: Mapping[str, str | list[str]]) -> bool:
    has_identity = any(_has_value(fields.get(name)) for name in _IDENTITY_FIELDS)
    has_detail = any(
        name not in _IDENTITY_FIELDS and _has_value(value)
        for name, value in fields.items()
    )
    return has_identity and has_detail


def _has_value(value: str | list[str] | None) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _store_extra_field(extra_fields: dict[str, str], label: str, value: str) -> None:
    key = label
    suffix = 2
    while key in extra_fields:
        key = f"{label}#{suffix}"
        suffix += 1
    extra_fields[key] = value
