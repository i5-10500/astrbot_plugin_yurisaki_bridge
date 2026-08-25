# SPDX-FileCopyrightText: 2026 i5-10500
# SPDX-License-Identifier: AGPL-3.0-or-later

"""JSON-serializable data models shared by bridge layers."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class BridgeError:
    """A stable error safe to return to an Agent."""

    error_type: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """Return the public error representation."""
        return {"type": self.error_type, "message": self.message}


@dataclass(frozen=True, slots=True)
class ImageReference:
    """A remote image reference extracted without downloading image data."""

    file: str | None = None
    url: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Return only safe, bounded OneBot image metadata."""
        return {"file": self.file, "url": self.url}


@dataclass(slots=True)
class SongInfoResult:
    """Structured result produced from one Yurisaki ``/a info`` response."""

    query: str
    raw_text: str
    ok: bool = True
    canonical_title: str | None = None
    song_id: str | None = None
    difficulties: list[str] = field(default_factory=list)
    note_counts: list[str] = field(default_factory=list)
    charters: list[str] = field(default_factory=list)
    side: str | None = None
    artist: str | None = None
    bpm: str | None = None
    version: str | None = None
    release_date: str | None = None
    pack: str | None = None
    images: list[ImageReference] = field(default_factory=list)
    extra_fields: dict[str, str] = field(default_factory=dict)
    error: BridgeError | None = None

    def to_dict(self) -> dict[str, Any]:
        """Build the stable public payload consumed by an Agent."""
        payload: dict[str, Any] = {
            "ok": self.ok,
            "source": "Yurisaki",
            "query": self.query,
            "raw_text": self.raw_text,
            "images": [image.to_dict() for image in self.images],
        }
        if not self.ok:
            if self.error is not None:
                payload["error"] = self.error.to_dict()
            return payload

        payload.update(
            {
                "canonical_title": self.canonical_title,
                "song_id": self.song_id,
                "difficulties": list(self.difficulties),
                "note_counts": list(self.note_counts),
                "charters": list(self.charters),
                "side": self.side,
                "artist": self.artist,
                "bpm": self.bpm,
                "version": self.version,
                "release_date": self.release_date,
                "pack": self.pack,
                "extra_fields": dict(self.extra_fields),
            }
        )
        return payload


@dataclass(slots=True)
class RandomSongResult:
    """Structured result produced from one Yurisaki ``/a rand`` response."""

    raw_text: str
    ok: bool = True
    filter_type: str | None = None
    filter_value: str | None = None
    canonical_title: str | None = None
    song_id: str | None = None
    difficulties: list[str] = field(default_factory=list)
    note_counts: list[str] = field(default_factory=list)
    charters: list[str] = field(default_factory=list)
    side: str | None = None
    artist: str | None = None
    bpm: str | None = None
    version: str | None = None
    release_date: str | None = None
    pack: str | None = None
    images: list[ImageReference] = field(default_factory=list)
    extra_fields: dict[str, str] = field(default_factory=dict)
    image_delivered: bool = False
    error: BridgeError | None = None

    def to_dict(self) -> dict[str, Any]:
        """Build the Tool payload without exposing temporary media values."""
        payload: dict[str, Any] = {
            "ok": self.ok,
            "source": "Yurisaki",
            "command": "rand",
            "filter": (
                {"type": self.filter_type, "value": self.filter_value}
                if self.filter_type is not None and self.filter_value is not None
                else None
            ),
            "raw_text": self.raw_text,
            "image_count": len(self.images),
            "image_delivered": self.image_delivered,
        }
        if not self.ok:
            if self.error is not None:
                payload["error"] = self.error.to_dict()
            return payload

        payload.update(
            {
                "canonical_title": self.canonical_title,
                "song_id": self.song_id,
                "difficulties": list(self.difficulties),
                "note_counts": list(self.note_counts),
                "charters": list(self.charters),
                "side": self.side,
                "artist": self.artist,
                "bpm": self.bpm,
                "version": self.version,
                "release_date": self.release_date,
                "pack": self.pack,
                "extra_fields": dict(self.extra_fields),
            }
        )
        return payload
