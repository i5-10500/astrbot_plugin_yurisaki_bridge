"""Unit tests for defensive OneBot and Yurisaki response parsing."""

import json
from pathlib import Path
from typing import Any

from yurisaki_bridge.parser import (
    extract_message_content,
    parse_random_song_response,
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
        "side": None,
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
        [_text_segment("曲目: Test\nBPM: 180\n新字段: alpha\n新字段: beta")],
    )

    assert result.ok is True
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


def test_nonempty_unrelated_text_is_not_success() -> None:
    result = parse_song_info_response(
        "test", [_text_segment("服务暂时繁忙，请稍后再试")]
    )

    assert result.ok is False
    assert result.canonical_title is None
    assert result.raw_text == "服务暂时繁忙，请稍后再试"
    assert result.error is not None
    assert result.error.error_type == "invalid_response"


def test_partial_valid_info_is_success() -> None:
    result = parse_song_info_response(
        "test",
        [_text_segment("曲目: Test Song\nBPM: 180")],
    )

    assert result.ok is True
    assert result.canonical_title == "Test Song"
    assert result.bpm == "180"


def test_valid_info_with_unknown_fields_is_success() -> None:
    result = parse_song_info_response(
        "test",
        [_text_segment("曲目ID: 42\n曲师: Test Artist\n未来字段: value")],
    )

    assert result.ok is True
    assert result.song_id == "42"
    assert result.artist == "Test Artist"
    assert result.extra_fields == {"未来字段": "value"}


def test_invalid_response_keeps_raw_text() -> None:
    payload = parse_song_info_response(
        "test",
        [_text_segment("提示: 服务暂时繁忙")],
    ).to_dict()

    assert payload["ok"] is False
    assert payload["raw_text"] == "提示: 服务暂时繁忙"
    assert payload["error"]["type"] == "invalid_response"


def test_empty_response_is_invalid() -> None:
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


def test_rand_parser_text_and_image() -> None:
    segments = json.loads(
        (FIXTURES / "yurisaki_rand_response.json").read_text(encoding="utf-8")
    )

    payload = parse_random_song_response(segments).to_dict()

    assert payload == {
        "ok": True,
        "source": "Yurisaki",
        "command": "rand",
        "raw_text": (
            "为您推荐的曲目是：\n曲目：Hypnotize\n"
            "难度：3.5 / 7.0 / 8.9 / 9.9\n物量：518 / 761 / 993 / 1164\n"
            "谱面设计：én / én / én / én × nitro「The Radical」\n"
            "曲侧：Conflict\n艺术家：rejection\nBPM：160\n版本：5.9\n"
            "上线日期：2024-07-30\n曲包：Absolute Nihil"
        ),
        "image_count": 1,
        "image_delivered": False,
        "canonical_title": "Hypnotize",
        "song_id": None,
        "difficulties": ["3.5", "7.0", "8.9", "9.9"],
        "note_counts": ["518", "761", "993", "1164"],
        "charters": ["én", "én", "én", "én × nitro「The Radical」"],
        "side": "Conflict",
        "artist": "rejection",
        "bpm": "160",
        "version": "5.9",
        "release_date": "2024-07-30",
        "pack": "Absolute Nihil",
        "extra_fields": {},
    }


def test_rand_missing_image() -> None:
    result = parse_random_song_response([_text_segment("曲目：Test\n艺术家：Artist")])

    assert result.ok is False
    assert result.error is not None
    assert result.error.error_type == "incomplete_response"
    assert result.raw_text == "曲目：Test\n艺术家：Artist"


def test_rand_missing_text() -> None:
    result = parse_random_song_response([{"type": "image", "data": {"file": "cover"}}])

    assert result.ok is False
    assert result.error is not None
    assert result.error.error_type == "invalid_response"
    assert len(result.images) == 1


def test_rand_unknown_extra_segments_and_fields_are_tolerated() -> None:
    result = parse_random_song_response(
        [
            {"type": "future_media", "data": {"unknown": "value"}},
            {"type": "image", "data": {"url": "https://example.invalid/image"}},
            _text_segment("为您推荐的曲目是：\n曲目：Test\nBPM：180\n未来字段：值"),
        ]
    )

    assert result.ok is True
    assert result.canonical_title == "Test"
    assert result.extra_fields == {"未来字段": "值"}
