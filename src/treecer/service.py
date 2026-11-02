"""Task-rooted discussion operations; CLI and MCP share path and sudo rules."""

import uuid

from .errors import TreecerError
from .navigation import Navigator, Target
from .paths import absolute, display
from .store import transaction

STATUSES = ("讨论中", "已解决", "暂放", "已取消")


def title_value(value):
    if not isinstance(value, str) or not value.strip():
        raise TreecerError("INVALID_TITLE", "名称需要包含文字。")
    return value


class TreeService:
    def __init__(self, resolver, project=None, workspace=None):
        self.nav = Navigator(resolver, project, workspace)
        self.resolver = resolver
        self.database = self.nav.database

    def _require_node(self, target):
        if target.node is None:
            raise TreecerError(
                "NODE_REQUIRED",
                "请选择任务内的节点；可先用 task add 或 task use 选择任务。",
                target=self.nav.describe(target),
            )

    def _guard(self, target, sudo):
        self._require_node(target)
        same = (
            target.project["id"] == self.nav.project["id"]
            and self.nav.task
            and target.task["id"] == self.nav.task["id"]
        )
        if not same and not sudo:
            current = f"{self.nav.task['title'] if self.nav.task else '-'}@{self.nav.project['name']}"
            owner = f"{target.task['title']}@{target.project['name']}"
            relative = "~" + absolute(target.parts[2:]) if target.parts[2:] else "~"
            correction = (
                f"若本意是当前任务，请核对 {relative} 并修正任务归属。"
                if self.nav.task
                else "当前尚未选择任务，也可先用 task use 选择目标任务。"
            )
            raise TreecerError(
                "SUDO_REQUIRED",
                f"本次修改未执行。你正在尝试修改 {owner} 的 {relative}。"
                f"当前任务是 {current}。确认目标后，请使用 treecer sudo 重试原指令；"
                + correction,
                current_task=current,
                target=self.nav.describe(target),
                current_task_candidate=relative if self.nav.task else None,
                retry="treecer sudo <原指令>",
            )

    def _revision(self, db, alias):
        db.execute(f"UPDATE {alias}.revision_clock SET value=value+1")
        return db.execute(f"SELECT value FROM {alias}.revision_clock").fetchone()[0]

    def _fresh(self, db, alias, target):
        row = db.execute(
            f"SELECT * FROM {alias}.nodes WHERE id=?", (target.node["id"],)
        ).fetchone()
        if row is None or row["task_id"] != target.task["id"]:
            raise TreecerError(
                "TARGET_CHANGED",
                "目标已移动，请重新读取路径后操作。",
                path=absolute(target.parts),
            )
        return row

    def _check_revision(self, row, revision, target):
        if row["revision"] != revision:
            latest = self.nav.node_value(
                Target(
                    target.parts,
                    target.project,
                    target.database,
                    target.task,
                    dict(row),
                )
            )
            raise TreecerError(
                "REVISION_CONFLICT",
                "节点已更新，请合并最新内容后提交。",
                current=latest,
            )

    def _unique(self, db, alias, parent, title, except_id=None):
        row = db.execute(
            f"SELECT id FROM {alias}.nodes WHERE parent_id=? AND title=?",
            (parent, title),
        ).fetchone()
        if row and row["id"] != except_id:
            raise TreecerError(
                "DUPLICATE_NAME",
                "同一父节点下已有该名称，请选择不同名称或更新已有节点。",
                title=title,
            )

    def _ancestors(self, target):
        start = 2 if target.node else 0
        return [
            {
                "title": "~"
                if index == 2 and target.parts[:2] == self.nav.home
                else target.parts[index - 1]
                if index
                else "/",
                "path": display(target.parts[:index], self.nav.home),
            }
            for index in range(start, len(target.parts) + 1)
        ]

    def _children(self, target, limit=50, offset=0):
        if limit < 1 or offset < 0:
            raise TreecerError("INVALID_PAGE", "limit 需要大于零，offset 需要非负。")
        if target.project is None:
            items = self.resolver.projects()
            rows = [
                {"title": item["title"], "path": item["path"], "kind": "project"}
                for item in items
            ]
            page = rows[offset : offset + limit + 1]
        elif target.task is None:
            with transaction(target.database) as (db, _):
                rows = db.execute(
                    "SELECT title FROM tasks ORDER BY id LIMIT ? OFFSET ?",
                    (limit + 1, offset),
                ).fetchall()
            page = [
                {
                    "title": row["title"],
                    "path": display(
                        [target.project["name"], row["title"]], self.nav.home
                    ),
                    "kind": "task",
                }
                for row in rows
            ]
        else:
            with transaction(target.database) as (db, _):
                rows = db.execute(
                    "SELECT * FROM nodes WHERE parent_id=? ORDER BY created,id LIMIT ? OFFSET ?",
                    (target.node["id"], limit + 1, offset),
                ).fetchall()
            page = [
                self.nav.node_value(
                    Target(
                        [*target.parts, row["title"]],
                        target.project,
                        target.database,
                        target.task,
                        dict(row),
                    ),
                    summary=True,
                )
                for row in rows
            ]
        return {
            "children": page[:limit],
            "next_offset": offset + limit if len(page) > limit else None,
        }

    def get_context(self, path=None, limit=50, offset=0):
        target = self.nav.locate(path)
        data = {
            "node": self.nav.node_value(target) if target.node else None,
            "ancestors": self._ancestors(target),
            **self._children(target, limit, offset),
        }
        return self.nav.result(data, target)

    def show_children(self, path=None, limit=50, offset=0):
        target = self.nav.locate(path)
        return self.nav.result(self._children(target, limit, offset), target)

    def get_path(self, path=None):
        target = self.nav.locate(path)
        return self.nav.result({"ancestors": self._ancestors(target)}, target)

    def get_parent(self, path=None):
        target = self.nav.locate(path)
        if not target.parts:
            return self.nav.result({"parent": None, "ancestors": []}, target)
        parent = self.nav.locate_parts(target.parts[:-1])
        value = (
            self.nav.node_value(parent, summary=True)
            if parent.node
            else self.nav.describe(parent)
        )
        return self.nav.result(
            {"parent": value, "ancestors": self._ancestors(parent)}, target
        )

    def focus(self, path):
        target = self.nav.locate(path)
        with transaction(self.resolver.catalog, write=True) as (db, _):
            self.nav.save_position(db, target)
        return self.nav.result(
            {"node": self.nav.node_value(target) if target.node else None}, target
        )

    def list_tasks(self, project_path=None):
        target = self.nav.locate(project_path or absolute([self.nav.project["name"]]))
        if not target.project or target.task:
            raise TreecerError("INVALID_PATH", "任务列表需要项目路径，例如 /Project。")
        with transaction(target.database) as (db, _):
            tasks = [
                {
                    "title": row["title"],
                    "path": absolute([target.project["name"], row["title"]]),
                }
                for row in db.execute("SELECT title FROM tasks ORDER BY id")
            ]
        return self.nav.result({"tasks": tasks}, target)

    def use_task(self, title):
        target = self.nav.locate_parts([self.nav.project["name"], title])
        with transaction(self.resolver.catalog, write=True) as (db, _):
            db.execute(
                "INSERT INTO selections VALUES (?,?,?,?) ON CONFLICT(source,session,project_id) "
                "DO UPDATE SET task_id=excluded.task_id",
                (
                    self.nav.source,
                    self.nav.session,
                    self.nav.project["id"],
                    target.task["id"],
                ),
            )
        self.nav.refresh()
        return self.get_context()

    def create_task(self, title):
        title = title_value(title)
        with transaction(
            self.resolver.catalog, write=True, attachments=[self.database]
        ) as (db, aliases):
            alias = aliases[self.database]
            if db.execute(
                f"SELECT 1 FROM {alias}.tasks WHERE title=?", (title,)
            ).fetchone():
                raise TreecerError(
                    "DUPLICATE_NAME", "当前项目中已有同名任务。", title=title
                )
            task_id = db.execute(
                f"INSERT INTO {alias}.tasks(title) VALUES (?)", (title,)
            ).lastrowid
            node_id, revision = uuid.uuid4().hex, self._revision(db, alias)
            db.execute(
                f"INSERT INTO {alias}.nodes(id,task_id,title,revision,created) VALUES (?,?,'',?,?)",
                (node_id, task_id, revision, revision),
            )
            db.execute(
                "INSERT INTO selections VALUES (?,?,?,?) ON CONFLICT(source,session,project_id) "
                "DO UPDATE SET task_id=excluded.task_id",
                (self.nav.source, self.nav.session, self.nav.project["id"], task_id),
            )
        self.nav.refresh()
        return self.get_context()

    def add_node(self, title, parent=None, note="", sudo=False):
        title = title_value(title)
        target = self.nav.locate(parent)
        self._guard(target, sudo)
        with transaction(
            self.resolver.catalog, write=True, attachments=[target.database]
        ) as (db, aliases):
            alias = aliases[target.database]
            row = self._fresh(db, alias, target)
            self._unique(db, alias, row["id"], title)
            node_id, revision = uuid.uuid4().hex, self._revision(db, alias)
            db.execute(
                f"INSERT INTO {alias}.nodes VALUES (?,?,?,?,?,'讨论中',?,?)",
                (node_id, row["task_id"], row["id"], title, note, revision, revision),
            )
        created = self.nav.by_node(target.project, node_id)
        return self.nav.result(
            {"operation": "add", "node": self.nav.node_value(created)}, created
        )

    def update_node(
        self, path, revision, title=None, status=None, note=None, sudo=False
    ):
        target = self.nav.locate(path)
        self._guard(target, sudo)
        if title is not None:
            title_value(title)
            if target.node["parent_id"] is None:
                raise TreecerError(
                    "ROOT_OPERATION", "任务根保持为 ~；可修改其正文和状态。"
                )
        if status is not None and status not in STATUSES:
            raise TreecerError("INVALID_STATUS", "状态应为：" + "、".join(STATUSES))
        fields = {
            key: value
            for key, value in {"title": title, "status": status, "note": note}.items()
            if value is not None
        }
        with transaction(
            self.resolver.catalog, write=True, attachments=[target.database]
        ) as (db, aliases):
            alias = aliases[target.database]
            row = self._fresh(db, alias, target)
            self._check_revision(row, revision, target)
            if title is not None:
                self._unique(db, alias, row["parent_id"], title, row["id"])
            if fields:
                assignments = ",".join(f"{field}=?" for field in fields)
                version = self._revision(db, alias)
                db.execute(
                    f"UPDATE {alias}.nodes SET {assignments},revision=? WHERE id=?",
                    (*fields.values(), version, row["id"]),
                )
        changed = self.nav.by_node(target.project, target.node["id"])
        return self.nav.result(
            {"operation": "update", "node": self.nav.node_value(changed)}, changed
        )

    def move_node(self, path, new_parent, revision, sudo=False):
        source, destination = self.nav.locate(path), self.nav.locate(new_parent)
        self._guard(source, sudo)
        self._guard(destination, sudo)
        if source.node["parent_id"] is None:
            raise TreecerError("ROOT_OPERATION", "任务根保持原位；可以移动它的子分支。")
        with transaction(
            self.resolver.catalog,
            write=True,
            attachments=[source.database, destination.database],
        ) as (db, aliases):
            src, dst = aliases[source.database], aliases[destination.database]
            row = self._fresh(db, src, source)
            self._check_revision(row, revision, source)
            parent = self._fresh(db, dst, destination)
            branch = [
                dict(item)
                for item in db.execute(
                    f"WITH RECURSIVE branch(id) AS (SELECT ? UNION ALL SELECT n.id FROM {src}.nodes n "
                    f"JOIN branch b ON n.parent_id=b.id) SELECT n.* FROM {src}.nodes n JOIN branch b ON n.id=b.id "
                    "ORDER BY n.created,n.id",
                    (row["id"],),
                )
            ]
            if any(item["id"] == parent["id"] for item in branch):
                raise TreecerError("INVALID_MOVE", "节点不能移动到自己或后代之下。")
            self._unique(
                db, dst, parent["id"], row["title"], row["id"] if src == dst else None
            )
            if src == dst:
                for item in branch:
                    db.execute(
                        f"UPDATE {src}.nodes SET task_id=? WHERE id=?",
                        (parent["task_id"], item["id"]),
                    )
                db.execute(
                    f"UPDATE {src}.nodes SET parent_id=?,revision=? WHERE id=?",
                    (parent["id"], self._revision(db, src), row["id"]),
                )
            else:
                for item in branch:
                    version = self._revision(db, dst)
                    db.execute(
                        f"INSERT INTO {dst}.nodes VALUES (?,?,?,?,?,?,?,?)",
                        (
                            item["id"],
                            parent["task_id"],
                            parent["id"]
                            if item["id"] == row["id"]
                            else item["parent_id"],
                            item["title"],
                            item["note"],
                            item["status"],
                            version,
                            version,
                        ),
                    )
                for item in reversed(branch):
                    db.execute(f"DELETE FROM {src}.nodes WHERE id=?", (item["id"],))
                    db.execute(
                        "UPDATE positions SET node_project_id=? WHERE node_project_id=? AND node_id=?",
                        (destination.project["id"], source.project["id"], item["id"]),
                    )
        moved = self.nav.by_node(destination.project, source.node["id"])
        return self.nav.result(
            {"operation": "move", "node": self.nav.node_value(moved)}, moved
        )

    def find_nodes(self, query, path=None, limit=50, offset=0):
        if limit < 1 or offset < 0:
            raise TreecerError("INVALID_PAGE", "limit 需要大于零，offset 需要非负。")
        target = self.nav.locate(
            path or ("~" if self.nav.task else absolute([self.nav.project["name"]]))
        )
        projects = (
            [target.project]
            if target.project
            else [
                self.resolver.project_named(row["title"])
                for row in self.resolver.projects()
            ]
        )
        found = []
        for project in projects:
            database = self.nav.database_for(project)
            with transaction(database) as (db, _):
                if target.node:
                    sql = (
                        "WITH RECURSIVE branch(id) AS (SELECT ? UNION ALL SELECT n.id FROM nodes n "
                        "JOIN branch b ON n.parent_id=b.id) SELECT n.id FROM nodes n JOIN branch b ON n.id=b.id "
                        "WHERE instr(n.title,?)>0 ORDER BY n.created,n.id LIMIT ?"
                    )
                    args = (target.node["id"], query, offset + limit + 1)
                else:
                    sql = "SELECT id FROM nodes WHERE instr(title,?)>0 ORDER BY created,id LIMIT ?"
                    args = (query, offset + limit + 1)
                rows = db.execute(sql, args).fetchall()
            found.extend(
                self.nav.node_value(self.nav.by_node(project, row["id"]), summary=True)
                for row in rows
            )
        return self.nav.result(
            {
                "matches": found[offset : offset + limit],
                "next_offset": offset + limit if len(found) > offset + limit else None,
            },
            target,
        )
