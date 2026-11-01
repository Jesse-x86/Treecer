"""SQLite ownership, schemas and transaction boundaries."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .errors import TreecerError


def data_home():
    if os.environ.get("TREECER_HOME"):
        return Path(os.environ["TREECER_HOME"]).expanduser().resolve()
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return base / "Treecer"


@contextmanager
def transaction(path: Path, *, write=False):
    connection = sqlite3.connect(path, timeout=15, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield connection
        connection.commit()
    except sqlite3.OperationalError as error:
        connection.rollback()
        if "locked" in str(error) or "busy" in str(error):
            raise TreecerError("STORE_BUSY", "数据库正忙，请稍后重试。") from error
        raise
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize(path: Path, schema: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=15) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            raise TreecerError("SCHEMA_VERSION", "此数据库由更新版本创建，请更新 Treecer。")
        if version == 1:
            return
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(schema)
        connection.execute("PRAGMA user_version=1")


CATALOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS workspaces (
    path TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id)
);
CREATE TABLE IF NOT EXISTS bindings (
    source TEXT NOT NULL, session TEXT NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(id), pinned INTEGER NOT NULL,
    PRIMARY KEY(source, session)
);
"""

PROJECT_SCHEMA = """
CREATE TABLE IF NOT EXISTS identity (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trees (
    id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER REFERENCES tasks(id),
    title TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tree_id INTEGER NOT NULL REFERENCES trees(id), parent_id INTEGER,
    title TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '讨论中'
        CHECK(status IN ('讨论中','已解决','暂放','已取消')),
    revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE(tree_id,id),
    FOREIGN KEY(tree_id,parent_id) REFERENCES nodes(tree_id,id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_root ON nodes(tree_id) WHERE parent_id IS NULL;
CREATE INDEX IF NOT EXISTS children ON nodes(tree_id,parent_id,id);
CREATE TABLE IF NOT EXISTS positions (
    source TEXT NOT NULL, session TEXT NOT NULL,
    task_id INTEGER REFERENCES tasks(id), tree_id INTEGER REFERENCES trees(id),
    node_id INTEGER REFERENCES nodes(id), PRIMARY KEY(source,session)
);
"""


def project_database(home: Path, project_id: str):
    path = home / "projects" / project_id / "project.sqlite"
    initialize(path, PROJECT_SCHEMA)
    with transaction(path, write=True) as connection:
        identity = connection.execute("SELECT id FROM identity").fetchone()
        if identity and identity["id"] != project_id:
            raise TreecerError("PROJECT_MISMATCH", "项目数据库身份与绑定不一致。")
        if not identity:
            connection.execute("INSERT INTO identity VALUES (?)", (project_id,))
    return path
