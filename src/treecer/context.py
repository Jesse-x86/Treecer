"""Automatic workspace discovery and persistent per-source session bindings."""

import json
import os
import uuid
from pathlib import Path

from .errors import TreecerError
from .store import data_home, initialize, project_database, transaction


def canonical(path):
    return os.path.normcase(str(Path(path).expanduser().resolve()))


def workspace_anchor(path):
    folder = Path(path).expanduser().resolve()
    for candidate in (folder, *folder.parents):
        if (candidate / ".treecer" / "project.json").exists() or (
            candidate / ".git"
        ).exists():
            return candidate
    return folder


class ContextResolver:
    def __init__(self, home=None, workspace=None, source="cli", session=None):
        self.home = Path(home).expanduser().resolve() if home else data_home()
        self.workspace = workspace
        self.source = source
        # CLI can reconnect by workspace. MCP supplies a generated or host session ID.
        self.session = (
            session
            or os.environ.get("TREECER_SESSION")
            or (
                "workspace:" + canonical(workspace_anchor(workspace))
                if workspace
                else "unbound"
            )
        )
        self.catalog = self.home / "catalog.sqlite"
        initialize(self.catalog)

    def projects(self):
        from .paths import absolute

        with transaction(self.catalog) as (connection, _):
            return [
                {"title": row["name"], "path": absolute([row["name"]])}
                for row in connection.execute("SELECT * FROM projects ORDER BY name")
            ]

    def project_named(self, name):
        with transaction(self.catalog) as (connection, _):
            row = connection.execute(
                "SELECT * FROM projects WHERE name=?", (name,)
            ).fetchone()
            if row is None:
                raise TreecerError("PROJECT_NOT_FOUND", f"找不到项目：{name}")
            return dict(row)

    def _project(self, connection, selector):
        rows = connection.execute(
            "SELECT * FROM projects WHERE id=? OR name=?", (selector, selector)
        ).fetchall()
        if len(rows) != 1:
            raise TreecerError("PROJECT_NOT_FOUND", f"找不到项目：{selector}")
        return dict(rows[0])

    def resolve(self, project=None, workspace=None):
        workspace = workspace or self.workspace
        with transaction(self.catalog, write=True) as (connection, _):
            binding = connection.execute(
                "SELECT * FROM bindings WHERE source=? AND session=?",
                (self.source, self.session),
            ).fetchone()
            if project:
                row = connection.execute(
                    "SELECT * FROM projects WHERE name=?", (project,)
                ).fetchone()
                if row is None:
                    raise TreecerError("PROJECT_NOT_FOUND", f"找不到项目：{project}")
                selected = dict(row)
                pinned = True
            elif binding and binding["pinned"]:
                selected = self._project(connection, binding["project_id"])
                pinned = True
            elif workspace:
                selected = self._discover(
                    connection, Path(workspace).expanduser().resolve()
                )
                pinned = False
            elif binding:
                selected = self._project(connection, binding["project_id"])
                pinned = False
            else:
                raise TreecerError(
                    "CONTEXT_REQUIRED",
                    "请提供实际工作区 workspace 或已登记项目 project；MCP 不推测服务启动目录。",
                )
            connection.execute(
                "INSERT INTO bindings VALUES (?,?,?,?) ON CONFLICT(source,session) "
                "DO UPDATE SET project_id=excluded.project_id,pinned=excluded.pinned",
                (self.source, self.session, selected["id"], int(pinned)),
            )
        database = project_database(self.home, selected["id"])
        return {
            **selected,
            "database": database,
            "source": self.source,
            "session": self.session,
            "pinned": pinned,
        }

    def _discover(self, connection, workspace):
        if not workspace.is_dir():
            raise TreecerError("WORKSPACE_NOT_FOUND", f"工作区目录不存在：{workspace}")
        root = workspace
        for folder in (workspace, *workspace.parents):
            marker = folder / ".treecer" / "project.json"
            if marker.exists():
                try:
                    content = json.loads(marker.read_text(encoding="utf-8"))
                    project_id = content["project_id"]
                    # IDs become path components; accept only our generated UUID form.
                    if uuid.UUID(project_id).hex != project_id:
                        raise ValueError("invalid project ID")
                except (ValueError, KeyError, TypeError) as error:
                    raise TreecerError(
                        "INVALID_MARKER", f"项目标记无效：{marker}"
                    ) from error
                selected = self._project(connection, project_id)
                connection.execute(
                    "INSERT INTO workspaces VALUES (?,?) ON CONFLICT(path) "
                    "DO UPDATE SET project_id=excluded.project_id",
                    (canonical(folder), project_id),
                )
                return selected
            registered = connection.execute(
                "SELECT project_id FROM workspaces WHERE path=?", (canonical(folder),)
            ).fetchone()
            if registered:
                return self._project(connection, registered["project_id"])
            if (folder / ".git").exists():
                root = folder
                break
        project_id = uuid.uuid4().hex
        base = root.name or "project"
        name = base
        suffix = 2
        while connection.execute(
            "SELECT 1 FROM projects WHERE name=?", (name,)
        ).fetchone():
            name = f"{base}-{suffix}"
            suffix += 1
        connection.execute("INSERT INTO projects VALUES (?,?)", (project_id, name))
        connection.execute(
            "INSERT INTO workspaces VALUES (?,?)", (canonical(root), project_id)
        )
        marker = root / ".treecer" / "project.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents silently replacing another process's marker.
        try:
            with marker.open("x", encoding="utf-8") as stream:
                json.dump({"project_id": project_id}, stream)
        except FileExistsError as error:
            raise TreecerError(
                "WORKSPACE_CHANGED", "工作区标记刚刚变化，请重新调用。"
            ) from error
        return {"id": project_id, "name": name}

    def reset(self):
        with transaction(self.catalog, write=True) as (connection, _):
            connection.execute(
                "DELETE FROM bindings WHERE source=? AND session=?",
                (self.source, self.session),
            )
        return {"reset": True, "source": self.source, "session": self.session}
