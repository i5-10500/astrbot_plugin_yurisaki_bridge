"""Checks for the repository scaffold shared by later milestones."""

import json
import re
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


def test_repository_uses_agpl_v3_or_later() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    runtime_files = [
        ROOT / "main.py",
        *sorted((ROOT / "yurisaki_bridge").glob("*.py")),
    ]

    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in license_text
    assert "Version 3, 19 November 2007" in license_text
    assert "AGPL-3.0-or-later" in readme
    assert "Copyright (C) 2026 `i5-10500`" in readme
    for runtime_file in runtime_files:
        source = runtime_file.read_text(encoding="utf-8")
        assert "SPDX-FileCopyrightText: 2026 i5-10500" in source
        assert "SPDX-License-Identifier: AGPL-3.0-or-later" in source


def test_public_docs_do_not_contain_test_release_residue() -> None:
    public_docs = [
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        ROOT / "SECURITY.md",
        ROOT / "docs" / "REAL_INTEGRATION.md",
        ROOT / "tests" / "fixtures" / "README.md",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml",
    ]
    forbidden_terms = (
        "beta",
        "私有仓库",
        "-test.zip",
        "Milestone 4",
        "7795cea",
    )

    for public_doc in public_docs:
        text = public_doc.read_text(encoding="utf-8")
        for forbidden_term in forbidden_terms:
            assert forbidden_term not in text


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
    assert schema["timeout_quarantine_seconds"]["default"] >= 0
    assert schema["debug_logging"]["default"] is False


def test_ci_actions_are_pinned_to_full_commit_shas() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    action_refs = re.findall(r"uses:\s+[^@\s]+@([^\s#]+)", workflow)

    assert len(action_refs) == 2
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)
