"""Project-scoped operations shared by command line and MCP adapters."""

from .errors import TreecerError
from .store import transaction

STATUSES = ("讨论中", "已解决", "暂放", "已取消")


def number(value, prefix):
    try:
        text = str(value)
        if text.startswith(prefix):
            text = text[1:]
        result = int(text)
        if result < 1:
            raise ValueError
        return result
    except (ValueError, TypeError) as error:
        raise TreecerError("INVALID_ID", f"无效的 {prefix} ID：{value}") from error


def named(row, prefix):
    return {**dict(row), "id": f"{prefix}{row['id']}"}


def node_data(row):
    return {**named(row, "N"), "tree_id": f"R{row['tree_id']}",
            "parent_id": f"N{row['parent_id']}" if row["parent_id"] else None}


def nonempty(value):
    if not isinstance(value, str) or not value.strip():
        raise TreecerError("INVALID_TITLE", "标题需要包含文字。")
    return value


class TreeService:
    def __init__(self, resolver, project=None, workspace=None):
        self.context = resolver.resolve(project, workspace)
        self.database = self.context["database"]
        self.source, self.session = self.context["source"], self.context["session"]

    def _position(self, connection):
        row = connection.execute("SELECT * FROM positions WHERE source=? AND session=?",
                                 (self.source, self.session)).fetchone()
        return dict(row) if row else {"task_id": None, "tree_id": None, "node_id": None}

    def _task(self, connection, selector):
        # Prefer exact ID syntax; otherwise return the unique exact-title match.
        if str(selector).startswith("T") and str(selector)[1:].isdigit():
            rows = connection.execute("SELECT * FROM tasks WHERE id=?",
                                      (number(selector, "T"),)).fetchall()
        else:
            rows = connection.execute("SELECT * FROM tasks WHERE title=?", (selector,)).fetchall()
        if not rows:
            raise TreecerError("TASK_NOT_FOUND", f"找不到任务：{selector}")
        if len(rows) > 1:
            raise TreecerError("AMBIGUOUS_TASK", "存在同名任务，请使用 ID。",
                               matches=[named(row, "T") for row in rows])
        return rows[0]

    def _tree(self, connection, tree_id):
        row = connection.execute("SELECT * FROM trees WHERE id=?", (number(tree_id, "R"),)).fetchone()
        if row is None:
            raise TreecerError("TREE_NOT_FOUND", f"当前项目中找不到树：{tree_id}")
        return row

    def _node(self, connection, node_id=None, tree_id=None):
        if node_id is None:
            position = self._position(connection)
            if tree_id:
                tree = self._tree(connection, tree_id)
                row = connection.execute("SELECT * FROM nodes WHERE tree_id=? AND parent_id IS NULL",
                                         (tree["id"],)).fetchone()
                return row
            node_id = position["node_id"]
        if node_id is None:
            raise TreecerError("NODE_REQUIRED", "请先选择节点，或创建/选择一棵树。")
        row = connection.execute("SELECT * FROM nodes WHERE id=?", (number(node_id, "N"),)).fetchone()
        if row is None:
            raise TreecerError("NODE_NOT_FOUND", f"当前项目中找不到节点：{node_id}")
        if tree_id and row["tree_id"] != number(tree_id, "R"):
            raise TreecerError("TREE_MISMATCH", "节点不属于指定的讨论树。")
        return row

    def _path(self, connection, row):
        path = []
        while row is not None:
            path.append({"id": f"N{row['id']}", "title": row["title"], "status": row["status"]})
            row = (connection.execute("SELECT * FROM nodes WHERE id=?", (row["parent_id"],)).fetchone()
                   if row["parent_id"] else None)
        return list(reversed(path))

    def _save_position(self, connection, task_id, tree_id=None, node_id=None):
        connection.execute(
            "INSERT INTO positions VALUES (?,?,?,?,?) ON CONFLICT(source,session) "
            "DO UPDATE SET task_id=excluded.task_id,tree_id=excluded.tree_id,node_id=excluded.node_id",
            (self.source, self.session, task_id, tree_id, node_id),
        )

    def _result(self, connection, data, row=None):
        position = self._position(connection)
        if row is None and position["node_id"]:
            row = self._node(connection, position["node_id"])
        tree = self._tree(connection, row["tree_id"]) if row else None
        task_id = tree["task_id"] if tree else position["task_id"]
        task = connection.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone() if task_id else None
        path = self._path(connection, row) if row else []
        # Quote path separators for display; the structured path preserves titles exactly.
        display = "/".join(item["title"].replace("%", "%25").replace("/", "%2F")
                           .replace("\n", "%0A").replace("\r", "%0D") for item in path)
        prompt = f"{task['title'] if task else '~'}@{self.context['name']}# {display or '/'}"
        if row:
            prompt += f" [N{row['id']}]"
        return {"project": {"id": self.context["id"], "name": self.context["name"]},
                "task": named(task, "T") if task else None,
                "tree": {**named(tree, "R"), "task_id": f"T{task_id}" if task_id else None} if tree else None,
                "source": self.source, "session": self.session, "prompt": prompt, **data}

    def get_context(self, node_id=None, tree_id=None, limit=50, offset=0):
        with transaction(self.database) as connection:
            position = self._position(connection)
            if node_id is None and tree_id is None and position["node_id"] is None:
                return self._result(connection, {
                    "node": None, "path": [], "children": [],
                    "tasks": [named(r, "T") for r in connection.execute("SELECT * FROM tasks ORDER BY id")],
                    "trees": self._trees(connection, position["task_id"]),
                })
            row = self._node(connection, node_id, tree_id)
            return self._result(connection, {"node": node_data(row), "path": self._path(connection, row),
                                            **self._children(connection, row, limit, offset)}, row)

    def _children(self, connection, row, limit, offset):
        if limit < 1 or offset < 0:
            raise TreecerError("INVALID_PAGE", "limit 需要大于零，offset 需要非负。")
        rows = connection.execute(
            "SELECT id,title,status FROM nodes WHERE parent_id=? AND tree_id=? ORDER BY id LIMIT ? OFFSET ?",
            (row["id"], row["tree_id"], limit + 1, offset),
        ).fetchall()
        return {"children": [named(r, "N") for r in rows[:limit]],
                "next_offset": offset + limit if len(rows) > limit else None}

    def show_children(self, node_id=None, tree_id=None, limit=50, offset=0):
        with transaction(self.database) as connection:
            row = self._node(connection, node_id, tree_id)
            return self._result(connection, self._children(connection, row, limit, offset), row)

    def get_path(self, node_id=None, tree_id=None):
        with transaction(self.database) as connection:
            row = self._node(connection, node_id, tree_id)
            return self._result(connection, {"path": self._path(connection, row)}, row)

    def get_parent(self, node_id=None, tree_id=None):
        with transaction(self.database) as connection:
            row = self._node(connection, node_id, tree_id)
            path = self._path(connection, row)[:-1]
            return self._result(connection, {"parent": path[-1] if path else None, "path": path}, row)

    def create_task(self, title):
        with transaction(self.database, write=True) as connection:
            task_id = connection.execute("INSERT INTO tasks(title) VALUES (?)", (nonempty(title),)).lastrowid
            self._save_position(connection, task_id)
            return self._result(connection, {"created": f"T{task_id}"})

    def list_tasks(self):
        with transaction(self.database) as connection:
            return self._result(connection, {"tasks": [named(row, "T") for row in
                                  connection.execute("SELECT * FROM tasks ORDER BY id")]})

    def _trees(self, connection, task_id):
        rows = connection.execute("SELECT * FROM trees WHERE task_id IS ? ORDER BY id", (task_id,))
        return [{**named(row, "R"), "task_id": f"T{row['task_id']}" if row["task_id"] else None}
                for row in rows]

    def list_trees(self, task=None, project_level=False):
        with transaction(self.database) as connection:
            task_id = (None if project_level else self._task(connection, task)["id"] if task
                       else self._position(connection)["task_id"])
            return self._result(connection, {"trees": self._trees(connection, task_id)})

    def create_tree(self, title, task=None, project_level=False, note=""):
        with transaction(self.database, write=True) as connection:
            task_id = (None if project_level else self._task(connection, task)["id"] if task
                       else self._position(connection)["task_id"])
            title = nonempty(title)
            tree_id = connection.execute("INSERT INTO trees(task_id,title) VALUES (?,?)", (task_id, title)).lastrowid
            node_id = connection.execute("INSERT INTO nodes(tree_id,title,note) VALUES (?,?,?)",
                                         (tree_id, title, note)).lastrowid
            self._save_position(connection, task_id, tree_id, node_id)
            row = self._node(connection, node_id)
            return self._result(connection, {"node": node_data(row)}, row)

    def focus(self, node_id=None, tree_id=None, task=None, project_level=False):
        with transaction(self.database, write=True) as connection:
            if task and (node_id or tree_id):
                row = self._node(connection, node_id, tree_id)
                if self._tree(connection, row["tree_id"])["task_id"] != self._task(connection, task)["id"]:
                    raise TreecerError("TASK_MISMATCH", "节点不属于指定任务。")
            elif node_id == "..":
                current = self._node(connection)
                row = self._node(connection, current["parent_id"] or current["id"])
            elif node_id or tree_id:
                row = self._node(connection, node_id, tree_id)
            else:
                task_id = self._task(connection, task)["id"] if task else (
                    None if project_level else self._position(connection)["task_id"])
                self._save_position(connection, task_id)
                return self._result(connection, {"focused": True})
            tree = self._tree(connection, row["tree_id"])
            self._save_position(connection, tree["task_id"], tree["id"], row["id"])
            return self._result(connection, {"node": node_data(row), "path": self._path(connection, row)}, row)

    def add_node(self, title, parent_id=None, tree_id=None, note=""):
        with transaction(self.database, write=True) as connection:
            parent = self._node(connection, parent_id, tree_id)
            node_id = connection.execute("INSERT INTO nodes(tree_id,parent_id,title,note) VALUES (?,?,?,?)",
                                         (parent["tree_id"], parent["id"], nonempty(title), note)).lastrowid
            row = self._node(connection, node_id)
            return self._result(connection, {"node": node_data(row)}, row)

    def _check_revision(self, row, revision):
        if row["revision"] != revision:
            raise TreecerError("REVISION_CONFLICT", "节点已被其他调用更新，请读取最新内容后合并。",
                               current=node_data(row))

    def update_node(self, node_id, revision, title=None, status=None, note=None, tree_id=None):
        with transaction(self.database, write=True) as connection:
            row = self._node(connection, node_id, tree_id)
            self._check_revision(row, revision)
            fields = {key: value for key, value in {"title": title, "status": status, "note": note}.items()
                      if value is not None}
            if "title" in fields:
                nonempty(title)
            if status is not None and status not in STATUSES:
                raise TreecerError("INVALID_STATUS", "状态应为：" + "、".join(STATUSES))
            if fields:
                assignments = ",".join(f"{key}=?" for key in fields)
                connection.execute(f"UPDATE nodes SET {assignments},revision=revision+1 WHERE id=?",
                                   (*fields.values(), row["id"]))
            row = self._node(connection, row["id"])
            return self._result(connection, {"node": node_data(row)}, row)

    def move_node(self, node_id, new_parent_id, revision, tree_id=None):
        with transaction(self.database, write=True) as connection:
            row = self._node(connection, node_id, tree_id)
            self._check_revision(row, revision)
            parent = self._node(connection, new_parent_id, row["tree_id"])
            if row["parent_id"] is None:
                raise TreecerError("INVALID_MOVE", "根节点保持为树根；可以移动它的子分支。")
            if any(item["id"] == f"N{row['id']}" for item in self._path(connection, parent)):
                raise TreecerError("INVALID_MOVE", "节点不能移动到自己或后代之下。")
            connection.execute("UPDATE nodes SET parent_id=?,revision=revision+1 WHERE id=?",
                               (parent["id"], row["id"]))
            row = self._node(connection, row["id"])
            return self._result(connection, {"node": node_data(row), "path": self._path(connection, row)}, row)

    def find_nodes(self, query, tree_id=None, limit=50, offset=0):
        if limit < 1 or offset < 0:
            raise TreecerError("INVALID_PAGE", "limit 需要大于零，offset 需要非负。")
        with transaction(self.database) as connection:
            parameters = [query]
            clause = "instr(title,?) > 0"
            if tree_id:
                tree = self._tree(connection, tree_id)
                clause += " AND tree_id=?"
                parameters.append(tree["id"])
            rows = connection.execute(f"SELECT * FROM nodes WHERE {clause} ORDER BY id LIMIT ? OFFSET ?",
                                      (*parameters, limit + 1, offset)).fetchall()
            return self._result(connection, {
                "matches": [{"id": f"N{row['id']}", "title": row["title"], "status": row["status"],
                             "tree_id": f"R{row['tree_id']}", "path": self._path(connection, row)}
                            for row in rows[:limit]],
                "next_offset": offset + limit if len(rows) > limit else None,
            })
