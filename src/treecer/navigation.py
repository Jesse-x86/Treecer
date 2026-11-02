"""Resolve public paths and format current position independently of targets."""

from dataclasses import dataclass

from .errors import TreecerError
from .paths import absolute, display, normalize
from .store import project_database, transaction


@dataclass
class Target:
    parts: list
    project: dict | None = None
    database: object = None
    task: dict | None = None
    node: dict | None = None


class Navigator:
    def __init__(self, resolver, project=None, workspace=None):
        self.resolver = resolver
        self.context = resolver.resolve(project, workspace)
        self.source, self.session = self.context["source"], self.context["session"]
        self.project = {key: self.context[key] for key in ("id", "name")}
        self._prepared = {}
        self.database = self.database_for(self.project)
        self.refresh()

    def database_for(self, project):
        if project["id"] in self._prepared:
            return self._prepared[project["id"]]
        database = project_database(self.resolver.home, project["id"])
        with transaction(database) as (db, _):
            legacy = db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='legacy_positions'"
            ).fetchone()
        if legacy:
            with transaction(
                self.resolver.catalog, write=True, attachments=[database]
            ) as (db, aliases):
                alias = aliases[database]
                if db.execute(
                    f"SELECT 1 FROM {alias}.sqlite_master WHERE name='legacy_positions'"
                ).fetchone():
                    for row in db.execute(
                        f"SELECT * FROM {alias}.legacy_positions"
                    ).fetchall():
                        db.execute(
                            "INSERT OR IGNORE INTO selections VALUES (?,?,?,?)",
                            (
                                row["source"],
                                row["session"],
                                project["id"],
                                row["task_id"],
                            ),
                        )
                        db.execute(
                            "INSERT OR IGNORE INTO positions VALUES (?,?,?,?,?,?,NULL)",
                            (
                                row["source"],
                                row["session"],
                                project["id"],
                                row["task_id"],
                                project["id"],
                                row["node_id"],
                            ),
                        )
                    db.execute(f"DROP TABLE {alias}.legacy_positions")
        self._prepared[project["id"]] = database
        return database

    def project_by_id(self, project_id):
        with transaction(self.resolver.catalog) as (db, _):
            row = db.execute(
                "SELECT * FROM projects WHERE id=?", (project_id,)
            ).fetchone()
        if row is None:
            raise TreecerError("PROJECT_NOT_FOUND", "保存的位置所指项目不存在。")
        return dict(row)

    def refresh(self):
        with transaction(self.resolver.catalog) as (db, _):
            selection = db.execute(
                "SELECT task_id FROM selections WHERE source=? AND session=? AND project_id=?",
                (self.source, self.session, self.project["id"]),
            ).fetchone()
        self.task = None
        if selection:
            with transaction(self.database) as (db, _):
                row = db.execute(
                    "SELECT * FROM tasks WHERE id=?", (selection["task_id"],)
                ).fetchone()
                self.task = dict(row) if row else None

    @property
    def home(self):
        return [self.project["name"], self.task["title"]] if self.task else []

    def by_node(self, project, node_id):
        database = self.database_for(project)
        with transaction(database) as (db, _):
            row = db.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
            if row is None:
                raise TreecerError(
                    "NODE_NOT_FOUND", "保存的讨论位置已不存在，请重新选择路径。"
                )
            node = dict(row)
            task = dict(
                db.execute(
                    "SELECT * FROM tasks WHERE id=?", (row["task_id"],)
                ).fetchone()
            )
            titles = []
            while row["parent_id"]:
                titles.append(row["title"])
                row = db.execute(
                    "SELECT * FROM nodes WHERE id=?", (row["parent_id"],)
                ).fetchone()
        return Target(
            [project["name"], task["title"], *reversed(titles)],
            project,
            database,
            task,
            node,
        )

    def current(self):
        with transaction(self.resolver.catalog) as (db, _):
            row = db.execute(
                "SELECT * FROM positions WHERE source=? AND session=? AND project_id=? AND task_id=?",
                (
                    self.source,
                    self.session,
                    self.project["id"],
                    self.task["id"] if self.task else 0,
                ),
            ).fetchone()
        if row and row["node_id"]:
            return self.by_node(
                self.project_by_id(row["node_project_id"]), row["node_id"]
            )
        if row and row["namespace"]:
            return self.locate_parts(normalize(row["namespace"], [], []))
        return self.locate_parts(self.home or [self.project["name"]])

    def locate(self, path=None):
        current = self.current()
        return self.locate_parts(normalize(path, current.parts, self.home))

    def locate_parts(self, parts):
        if not parts:
            return Target([])
        project = self.resolver.project_named(parts[0])
        database = self.database_for(project)
        if len(parts) == 1:
            return Target(parts, project, database)
        with transaction(database) as (db, _):
            task = db.execute(
                "SELECT * FROM tasks WHERE title=?", (parts[1],)
            ).fetchone()
            if task is None:
                raise TreecerError(
                    "TASK_NOT_FOUND",
                    f"找不到任务：{parts[1]}",
                    path=absolute(parts[:2]),
                )
            row = db.execute(
                "SELECT * FROM nodes WHERE task_id=? AND parent_id IS NULL",
                (task["id"],),
            ).fetchone()
            for index, title in enumerate(parts[2:], 2):
                child = db.execute(
                    "SELECT * FROM nodes WHERE parent_id=? AND title=?",
                    (row["id"], title),
                ).fetchone()
                if child is None:
                    raise TreecerError(
                        "NODE_NOT_FOUND",
                        "找不到讨论节点。",
                        path=absolute(parts),
                        nearest_existing_path=display(parts[:index], self.home),
                    )
                row = child
        return Target(parts, project, database, dict(task), dict(row))

    def describe(self, target):
        return {
            "project": target.project["name"] if target.project else None,
            "task": target.task["title"] if target.task else None,
            "path": display(target.parts, self.home),
            "absolute_path": absolute(target.parts),
        }

    def node_value(self, target, *, summary=False):
        value = {
            "title": target.node["title"] or "/",
            "path": display(target.parts, self.home),
            "absolute_path": absolute(target.parts),
            "status": target.node["status"],
        }
        if not summary:
            value.update(
                note=target.node["note"],
                revision=target.node["revision"],
                parent=display(target.parts[:-1], self.home),
            )
        return value

    def result(self, data, target=None):
        current = self.current()
        location = self.describe(current)
        location.update(
            project=self.project["name"], task=self.task["title"] if self.task else None
        )
        return {
            "prompt": f"{self.task['title'] if self.task else '-'}@{self.project['name']}: {location['path']}$",
            "current": location,
            "source": self.source,
            "session": self.session,
            **({"target": self.describe(target)} if target else {}),
            **data,
        }

    def save_position(self, db, target):
        db.execute(
            "INSERT INTO positions VALUES (?,?,?,?,?,?,?) ON CONFLICT(source,session,project_id,task_id) "
            "DO UPDATE SET node_project_id=excluded.node_project_id,node_id=excluded.node_id,namespace=excluded.namespace",
            (
                self.source,
                self.session,
                self.project["id"],
                self.task["id"] if self.task else 0,
                target.project["id"] if target.node else None,
                target.node["id"] if target.node else None,
                None if target.node else absolute(target.parts),
            ),
        )
