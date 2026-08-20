"""Checks for the repository scaffold shared by later milestones."""

import json
from importlib import import_module
from pathlib import Path

import yaml

from yurisaki_bridge import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_metadata_matches_package_version() -> None:
    metadata = yaml.safe_load((ROOT / "metadata.yaml").read_text(encoding="utf-8"))

    assert metadata["name"] == "astrbot_plugin_yurisaki_bridge"
    assert metadata["version"] == __version__
    assert metadata["support_platforms"] == ["aiocqhttp"]


def test_architecture_modules_are_importable() -> None:
    for module_name in ("models", "parser", "service", "transport"):
        module = import_module(f"yurisaki_bridge.{module_name}")
        assert module.__doc__


def test_plugin_configuration_schema_has_safe_defaults() -> None:
    schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))

    assert schema["enabled"]["default"] is True
    assert schema["yurisaki_user_id"]["default"] == "3889054356"
    assert schema["timeout_seconds"]["default"] > 0
    assert schema["min_request_interval"]["default"] >= 0
    assert schema["debug_logging"]["default"] is False
