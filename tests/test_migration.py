"""Replay the released 0.1.1 disk schema, independently of the new schema."""

from contextlib import closing
import json
import sqlite3
import uuid

import pytest

from treecer.context import ContextResolver, canonical
from treecer.errors import TreecerError
from treecer.service import TreeService


OLD_CATALOG = """
CREATE TABLE projects(id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE);
CREATE TABLE workspaces(path TEXT PRIMARY KEY,project_id TEXT REFERENCES projects(id));
CREATE TABLE bindings(source TEXT,session TEXT,project_id TEXT REFERENCES projects(id),pinned INTEGER,
    PRIMARY KEY(source,session));
PRAGMA user_version=1;
"""
OLD_PROJECT = """
CREATE TABLE identity(id TEXT PRIMARY KEY);
CREATE TABLE tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL);
CREATE TABLE trees(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id INTEGER REFERENCES tasks(id),title TEXT NOT NULL);
CREATE TABLE nodes(id INTEGER PRIMARY KEY AUTOINCREMENT,tree_id INTEGER REFERENCES trees(id),parent_id INTEGER,
    title TEXT NOT NULL,note TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT '讨论中',revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE(tree_id,id),FOREIGN KEY(tree_id,parent_id) REFERENCES nodes(tree_id,id));
CREATE UNIQUE INDEX one_root ON nodes(tree_id) WHERE parent_id IS NULL;
CREATE TABLE positions(source TEXT,session TEXT,task_id INTEGER REFERENCES tasks(id),tree_id INTEGER REFERENCES trees(id),
    node_id INTEGER REFERENCES nodes(id),PRIMARY KEY(source,session));
PRAGMA user_version=1;
"""


def legacy(tmp_path):
    home, workspace = tmp_path / "data", tmp_path / "Project"
    workspace.mkdir()
    (workspace / ".treecer").mkdir()
    identity = uuid.uuid4().hex
    project = home / "projects" / identity / "project.sqlite"
    project.parent.mkdir(parents=True)
    (workspace / ".treecer/project.json").write_text(
        json.dumps({"project_id": identity}), encoding="utf-8"
    )
    with closing(sqlite3.connect(home / "catalog.sqlite")) as db:
        db.executescript(OLD_CATALOG)
        db.execute("INSERT INTO projects VALUES (?,?)", (identity, "Project"))
        db.execute(
            "INSERT INTO workspaces VALUES (?,?)", (canonical(workspace), identity)
        )
        db.execute("INSERT INTO bindings VALUES (?,?,?,0)", ("codex", "chat", identity))
        db.commit()
    with closing(sqlite3.connect(project)) as db:
        db.executescript(OLD_PROJECT)
        db.execute("INSERT INTO identity VALUES (?)", (identity,))
        db.executemany("INSERT INTO tasks VALUES (?,?)", [(1, "Topic"), (2, "empty")])
        db.executemany(
            "INSERT INTO trees VALUES (?,?,?)", [(1, 1, "设计"), (2, 1, "记录")]
        )
        db.executemany(
            "INSERT INTO nodes(id,tree_id,parent_id,title,note,status) VALUES (?,?,?,?,?,?)",
            [
                (1, 1, None, "设计", "用户已确定：保留全文", "讨论中"),
                (2, 1, 1, "方案比较", "助手建议：按场景比较方案", "暂放"),
                (3, 2, None, "记录", "待讨论：记录方式", "讨论中"),
            ],
        )
        db.execute(
            "INSERT INTO positions VALUES (?,?,?,?,?)", ("codex", "chat", 1, 1, 2)
        )
        db.commit()
    return home, workspace, project


def test_migrate_v1_preserves_content_empty_tasks_and_resume(tmp_path):
    home, workspace, path = legacy(tmp_path)
    service = TreeService(ContextResolver(home, workspace, "codex", "chat"))
    current = service.get_context()
    assert current["prompt"] == "Topic@Project: ~/设计/方案比较$"
    assert current["node"]["note"] == "助手建议：按场景比较方案"
    assert current["node"]["status"] == "暂放"
    assert service.get_context("~/设计")["node"]["note"] == "用户已确定：保留全文"
    assert [row["title"] for row in service.show_children("~")["children"]] == [
        "设计",
        "记录",
    ]
    identity = service.nav.locate().node["id"]
    reopened = TreeService(ContextResolver(home, workspace, "codex", "chat"))
    assert reopened.nav.locate().node["id"] == identity
    reopened.use_task("empty")
    assert reopened.get_context()["node"]["path"] == "~"
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name IN ('trees','legacy_positions')"
        ).fetchall()
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("conflict", ["task", "sibling", "topic"])
def test_conflicting_legacy_data_rolls_back_without_loss(tmp_path, conflict):
    home, workspace, path = legacy(tmp_path)
    with closing(sqlite3.connect(path)) as db:
        if conflict == "task":
            db.execute("INSERT INTO tasks(title) VALUES ('Topic')")
        elif conflict == "sibling":
            db.execute(
                "INSERT INTO nodes(tree_id,parent_id,title,note) VALUES (1,1,'方案比较','another record')"
            )
        else:
            db.execute("UPDATE nodes SET title='设计' WHERE id=3")
        db.commit()
        before = db.execute("SELECT * FROM nodes ORDER BY id").fetchall()
    with pytest.raises(TreecerError) as error:
        TreeService(ContextResolver(home, workspace, "codex", "chat"))
    assert error.value.code == "MIGRATION_CONFLICT"
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("SELECT * FROM nodes ORDER BY id").fetchall() == before
        assert (
            db.execute("SELECT node_id FROM positions WHERE source='codex'").fetchone()[
                0
            ]
            == 2
        )


def test_legacy_project_topics_get_an_inbox_without_overwriting_existing_task(tmp_path):
    home, workspace, path = legacy(tmp_path)
    with closing(sqlite3.connect(path)) as db:
        db.execute("INSERT INTO tasks(title) VALUES ('inbox')")
        db.execute("INSERT INTO trees VALUES (3,NULL,'灵感')")
        db.execute(
            "INSERT INTO nodes(tree_id,parent_id,title,note) VALUES (3,NULL,'灵感','original')"
        )
        db.commit()
    service = TreeService(ContextResolver(home, workspace, "codex", "chat"))
    assert "inbox (2)" in [row["title"] for row in service.list_tasks()["tasks"]]
    assert service.get_context("/Project/inbox (2)/灵感")["node"]["note"] == "original"
