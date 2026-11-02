import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


EXECUTABLE = Path(sys.executable).with_name("treecer.exe" if os.name == "nt" else "treecer")
TOPICS = ("quick-start", "core-concept", "workflow", "reference")


def read_doc(tmp_path, *arguments):
    return subprocess.run(
        [str(EXECUTABLE), "--home", str(tmp_path / "no-database"), "doc", *arguments],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=15,
    )


def test_list_languages_and_no_project_initialization(tmp_path):
    chinese = read_doc(tmp_path)
    english = read_doc(tmp_path, "--en")
    assert chinese.returncode == english.returncode == 0
    assert "快速开始" in chinese.stdout
    assert "Quick start" in english.stdout
    assert all(topic in chinese.stdout and topic in english.stdout for topic in TOPICS)
    assert not (tmp_path / "no-database").exists()
    assert not (tmp_path / ".treecer").exists()


@pytest.mark.parametrize("topic", TOPICS)
def test_read_both_languages_as_installed_resource(tmp_path, topic):
    chinese = read_doc(tmp_path, topic, "--json")
    english = read_doc(tmp_path, topic, "--en", "--json")
    assert chinese.returncode == english.returncode == 0
    zh, en = json.loads(chinese.stdout), json.loads(english.stdout)
    assert zh["language"] == "zh" and en["language"] == "en"
    assert zh["topic"] == en["topic"] == topic
    assert zh["content"].startswith("# " + zh["title"])
    assert en["content"].startswith("# " + en["title"])
    assert zh["content"] != en["content"]
    assert not (tmp_path / "no-database").exists()


def test_unknown_topic_and_flag_placement(tmp_path):
    failed = read_doc(tmp_path, "unknown-topic")
    assert failed.returncode != 0
    assert "unknown-topic" in failed.stderr
    english = read_doc(tmp_path, "--en", "quick-start")
    assert english.returncode == 0
    assert english.stdout.startswith("# Quick start")
    assert not (tmp_path / "no-database").exists()
