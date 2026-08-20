"""Unit tests for defensive OneBot and Yurisaki response parsing."""

import json
from pathlib import Path
from typing import Any

from yurisaki_bridge.parser import (
    extract_message_content,
    parse_song_info_response,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _text_segment(text: str) -> dict[str, Any]:
    return {"type": "text", "data": {"text": text}}


def test_parse_normal_song_info_with_image() -> None:
    segments = json.loads(
        (FIXTURES / "song_info_synthetic.json").read_text(encoding="utf-8")
    )

    payload = parse_song_info_response("synthesis", segments).to_dict()

    assert payload == {
        "ok": True,
        "source": "Yurisaki",
        "query": "synthesis",
        "raw_text": (
            "曲目：Synthesis.\n曲目ID：542\n难度：4.0 / 8.2 / 9.7 / 10.5\n"
            "物量：764 / 1109 / 1192 / 1469\n谱面设计：Charter A / Charter B\n"
            "曲师：tn-shi\nBPM：180\n版本：6.16\n上线日期：2026-07-30\n"
            "曲包：Memory Archive"
        ),
        "images": [
            {
                "file": "synthetic-synthesis-cover",
                "url": "https://example.invalid/synthesis.jpg",
            }
        ],
        "canonical_title": "Synthesis.",
        "song_id": "542",
        "difficulties": ["4.0", "8.2", "9.7", "10.5"],
        "note_counts": ["764", "1109", "1192", "1469"],
        "charters": ["Charter A", "Charter B"],
        "artist": "tn-shi",
        "bpm": "180",
        "version": "6.16",
        "release_date": "2026-07-30",
        "pack": "Memory Archive",
        "extra_fields": {},
    }
    json.dumps(payload, ensure_ascii=False)


def test_field_order_and_missing_fields_are_tolerated() -> None:
    result = parse_song_info_response(
        "test",
        [_text_segment("BPM: 180-200\n曲目: Test Song\n难度: 9 / 10")],
    )

    assert result.canonical_title == "Test Song"
    assert result.bpm == "180-200"
    assert result.difficulties == ["9", "10"]
    assert result.song_id is None


def test_unknown_and_duplicate_fields_are_preserved() -> None:
    result = parse_song_info_response(
        "test",
        [_text_segment("曲目: Test\n新字段: alpha\n新字段: beta")],
    )

    assert result.extra_fields == {"新字段": "alpha", "新字段#2": "beta"}


def test_scalar_field_value_containing_slash_is_not_split() -> None:
    result = parse_song_info_response(
        "test",
        [_text_segment("曲目: Test\n曲包: Collaboration / Memory Archive")],
    )

    assert result.pack == "Collaboration / Memory Archive"


def test_unicode_title_and_full_width_colon_are_supported() -> None:
    result = parse_song_info_response(
        "合成",
        [_text_segment("曲目：光（中国語版）\n曲师：Artist Ω")],
    )

    assert result.canonical_title == "光（中国語版）"
    assert result.artist == "Artist Ω"


def test_unexpected_text_degrades_to_raw_text() -> None:
    result = parse_song_info_response(
        "test", [_text_segment("服务暂时繁忙，请稍后再试")]
    )

    assert result.ok is True
    assert result.canonical_title is None
    assert result.raw_text == "服务暂时繁忙，请稍后再试"


def test_empty_text_returns_safe_failure() -> None:
    payload = parse_song_info_response(
        "test",
        [{"type": "image", "data": {"file": "cover"}}],
    ).to_dict()

    assert payload["ok"] is False
    assert payload["raw_text"] == ""
    assert payload["error"] == {
        "type": "invalid_response",
        "message": "Yurisaki response contained no text.",
    }


def test_multiple_text_and_image_segments_are_extracted_in_order() -> None:
    raw_text, images = extract_message_content(
        [
            _text_segment("曲目: "),
            {"type": "image", "data": {"file": "a"}},
            _text_segment("Test"),
            {"type": "image", "data": {"url": "https://example.invalid/b.jpg"}},
        ]
    )

    assert raw_text == "曲目: Test"
    assert [image.to_dict() for image in images] == [
        {"file": "a", "url": None},
        {"file": None, "url": "https://example.invalid/b.jpg"},
    ]


def test_large_or_unknown_image_data_is_not_retained() -> None:
    large_payload = "x" * 100_000
    _, images = extract_message_content(
        [
            {
                "type": "image",
                "data": {
                    "file": "safe-reference",
                    "base64": large_payload,
                    "unknown": large_payload,
                },
            }
        ]
    )

    assert images[0].to_dict() == {"file": "safe-reference", "url": None}
    assert large_payload not in repr(images[0])


def test_malformed_segments_are_ignored() -> None:
    raw_text, images = extract_message_content(
        [
            None,
            "not-a-segment",
            {"type": "text", "data": {"text": 123}},
            {"type": "image", "data": {"file": 456}},
            {"type": "unknown", "data": {"text": "ignored"}},
        ]
    )

    assert raw_text == ""
    assert images == []
