"""SQLite ownership, task roots and atomic operations across project files."""

import os
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from .errors import TreecerError


def data_home():
    if os.environ.get("TREECER_HOME"):
        return Path(os.environ["TREECER_HOME"]).expanduser().resolve()
    base = (
        Path(os.environ["LOCALAPPDATA"])
        if os.name == "nt" and os.environ.get("LOCALAPPDATA")
        else Path.home() / ".local" / "share"
    )
    return base / "Treecer"


@contextmanager
def transaction(path, *, write=False, attachments=()):
    connection = sqlite3.connect(path, timeout=15, isolation_level=None)
    connection.row_factory = sqlite3.Row
    aliases = {}
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        for index, attached in enumerate(
            dict.fromkeys(Path(p) for p in attachments), 1
        ):
            alias = f"p{index}"
            connection.execute(f"ATTACH DATABASE ? AS {alias}", (str(attached),))
            connection.execute(f"PRAGMA {alias}.synchronous=FULL")
            aliases[attached] = alias
        connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield connection, aliases
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


def execute_schema(connection, schema):
    for statement in schema.split(";"):
        if statement.strip():
            connection.execute(statement)


CATALOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS workspaces(path TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id));
CREATE TABLE IF NOT EXISTS bindings(source TEXT NOT NULL,session TEXT NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(id),pinned INTEGER NOT NULL,PRIMARY KEY(source,session));
CREATE TABLE IF NOT EXISTS selections(source TEXT NOT NULL,session TEXT NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(id),task_id INTEGER NOT NULL,
    PRIMARY KEY(source,session,project_id));
CREATE TABLE IF NOT EXISTS positions(source TEXT NOT NULL,session TEXT NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(id),task_id INTEGER NOT NULL,
    node_project_id TEXT REFERENCES projects(id),node_id TEXT,namespace TEXT,
    PRIMARY KEY(source,session,project_id,task_id));
"""

PROJECT_SCHEMA = """
CREATE TABLE IF NOT EXISTS identity(id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS nodes(
    id TEXT PRIMARY KEY,task_id INTEGER NOT NULL REFERENCES tasks(id),parent_id TEXT,
    title TEXT NOT NULL,note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '讨论中' CHECK(status IN ('讨论中','已解决','暂放','已取消')),
    revision INTEGER NOT NULL,created INTEGER NOT NULL,
    UNIQUE(task_id,id),UNIQUE(parent_id,title),
    FOREIGN KEY(task_id,parent_id) REFERENCES nodes(task_id,id) DEFERRABLE INITIALLY DEFERRED);
CREATE UNIQUE INDEX IF NOT EXISTS one_root ON nodes(task_id) WHERE parent_id IS NULL;
CREATE INDEX IF NOT EXISTS children ON nodes(task_id,parent_id,created);
CREATE TABLE IF NOT EXISTS revision_clock(value INTEGER NOT NULL);
INSERT INTO revision_clock SELECT 0 WHERE NOT EXISTS(SELECT 1 FROM revision_clock);
"""


def initialize(path, *, project_id=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=15, isolation_level=None)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > 2:
            raise TreecerError(
                "SCHEMA_VERSION", "此数据库由更新版本创建，请更新 Treecer。"
            )
        if project_id and version:
            identity = connection.execute("SELECT id FROM identity").fetchone()
            if not identity or identity["id"] != project_id:
                raise TreecerError("PROJECT_MISMATCH", "项目数据库身份与绑定不一致。")
        if version == 2:
            return
        # Rollback journals allow a single atomic commit across attached local files.
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute("PRAGMA defer_foreign_keys=ON")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if project_id and version == 1:
                from .migration import migrate_project

                migrate_project(connection, project_id)
            else:
                execute_schema(
                    connection, PROJECT_SCHEMA if project_id else CATALOG_SCHEMA
                )
            if project_id:
                connection.execute(
                    "INSERT OR IGNORE INTO identity VALUES (?)", (project_id,)
                )
            connection.execute("PRAGMA user_version=2")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


def project_database(home, project_id):
    path = Path(home) / "projects" / project_id / "project.sqlite"
    initialize(path, project_id=project_id)
    return path
