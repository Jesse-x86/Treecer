"""Transactional conversion from 0.1.1 trees to task-rooted discussions."""

import uuid

from .errors import TreecerError


def migrate_project(connection, project_id):
    tasks = [dict(row) for row in connection.execute("SELECT * FROM tasks ORDER BY id")]
    trees = {
        row["id"]: dict(row)
        for row in connection.execute("SELECT * FROM trees ORDER BY id")
    }
    nodes = [dict(row) for row in connection.execute("SELECT * FROM nodes ORDER BY id")]
    positions = [dict(row) for row in connection.execute("SELECT * FROM positions")]
    names = [row["title"] for row in tasks]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise TreecerError(
            "MIGRATION_CONFLICT",
            "旧数据有同名任务；迁移已撤销，原内容保留，需要先确定这些任务的新名称。",
            titles=duplicates,
        )
    if any(tree["task_id"] is None for tree in trees.values()):
        name, suffix = "inbox", 2
        while name in names:
            name, suffix = f"inbox ({suffix})", suffix + 1
        task_id = max((row["id"] for row in tasks), default=0) + 1
        tasks.append({"id": task_id, "title": name})
        for tree in trees.values():
            if tree["task_id"] is None:
                tree["task_id"] = task_id
    task_names = {row["id"]: row["title"] for row in tasks}
    seen = set()
    for row in nodes:
        key = (trees[row["tree_id"]]["task_id"], row["parent_id"], row["title"])
        if key in seen:
            raise TreecerError(
                "MIGRATION_CONFLICT",
                "旧数据迁移后会出现同父同名节点；迁移已撤销。",
                task=task_names[key[0]],
                title=row["title"],
            )
        seen.add(key)
    for table in ("positions", "nodes", "trees", "tasks"):
        connection.execute(f"DROP TABLE {table}")
    from .store import PROJECT_SCHEMA, execute_schema

    execute_schema(connection, PROJECT_SCHEMA)
    roots = {}
    for task in tasks:
        connection.execute(
            "INSERT INTO tasks(id,title) VALUES (?,?)", (task["id"], task["title"])
        )
        root_id = uuid.uuid5(uuid.UUID(project_id), f"task-root:{task['id']}").hex
        roots[task["id"]] = root_id
        connection.execute("UPDATE revision_clock SET value=value+1")
        revision = connection.execute("SELECT value FROM revision_clock").fetchone()[0]
        connection.execute(
            "INSERT INTO nodes(id,task_id,title,revision,created) VALUES (?,?,'',?,?)",
            (root_id, task["id"], revision, revision),
        )
    identities = {
        row["id"]: uuid.uuid5(uuid.UUID(project_id), f"node:{row['id']}").hex
        for row in nodes
    }
    for row in nodes:
        task_id = trees[row["tree_id"]]["task_id"]
        parent = identities[row["parent_id"]] if row["parent_id"] else roots[task_id]
        connection.execute("UPDATE revision_clock SET value=value+1")
        revision = connection.execute("SELECT value FROM revision_clock").fetchone()[0]
        connection.execute(
            "INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?)",
            (
                identities[row["id"]],
                task_id,
                parent,
                row["title"],
                row["note"],
                row["status"],
                revision,
                revision,
            ),
        )
    connection.execute(
        "CREATE TABLE legacy_positions(source TEXT,session TEXT,task_id INTEGER,node_id TEXT)"
    )
    node_tasks = {row["id"]: trees[row["tree_id"]]["task_id"] for row in nodes}
    for position in positions:
        task_id = node_tasks.get(position["node_id"], position["task_id"])
        if task_id in roots:
            node_id = identities.get(position["node_id"], roots[task_id])
            connection.execute(
                "INSERT INTO legacy_positions VALUES (?,?,?,?)",
                (position["source"], position["session"], task_id, node_id),
            )
