from concurrent.futures import ThreadPoolExecutor

import pytest

from treecer.context import ContextResolver
from treecer.errors import TreecerError
from treecer.service import TreeService


@pytest.fixture
def env(tmp_path):
    workspace = tmp_path / "Project"
    workspace.mkdir()
    home = tmp_path / "data"

    def make(source="codex", session="chat-1", folder=workspace):
        return TreeService(ContextResolver(home, folder, source, session))

    return make, home, workspace


def test_discussion_roundtrip_and_independent_source_positions(env):
    make, _, _ = env
    first = make()
    first.create_task("Topic")
    root = first.create_tree("方案讨论")["node"]
    a = first.add_node("方案比较")["node"]
    b = first.add_node("暂放问题", note="返回条件：方案比较讨论结束")["node"]
    first.update_node(b["id"], 1, status="暂放")
    first.focus(a["id"])
    leaf = first.add_node("比较标准", note="助手建议：按相关性筛选")["node"]
    first.focus(leaf["id"])
    second = make("other", "chat-1")
    assert second.get_context()["node"] is None
    second.focus(root["id"])
    assert make().get_context()["node"]["id"] == leaf["id"]
    assert make("other", "chat-1").get_context()["node"]["id"] == root["id"]
    context = first.get_context()
    assert context["prompt"] == f"Topic@Project# 方案讨论/方案比较/比较标准 [{leaf['id']}]"
    assert [item["id"] for item in context["path"]] == [root["id"], a["id"], leaf["id"]]
    first.update_node(leaf["id"], 1, status="已解决", note="用户已确定：保留候选细节")
    first.focus("..")
    assert first.get_parent()["parent"]["id"] == root["id"]
    first.focus("..")
    children = first.show_children()["children"]
    assert children == [
        {"id": a["id"], "title": "方案比较", "status": "讨论中"},
        {"id": b["id"], "title": "暂放问题", "status": "暂放"},
    ]


def test_ids_duplicate_names_rename_move_and_conflicts(env):
    make, _, _ = env
    service = make()
    root = service.create_tree("root")["node"]
    first = service.add_node("same")["node"]
    second = service.add_node("same")["node"]
    assert first["id"] != second["id"]
    leaf = service.add_node("a/b%", first["id"])["node"]
    service.focus(leaf["id"])
    changed = service.update_node(first["id"], 1, title="renamed")["node"]
    with pytest.raises(TreecerError, match="已被其他调用更新") as error:
        service.update_node(first["id"], 1, note="old snapshot")
    assert error.value.code == "REVISION_CONFLICT"
    assert error.value.details["current"]["revision"] == 2
    service.move_node(first["id"], second["id"], changed["revision"])
    context = make().get_context()
    assert [part["id"] for part in context["path"]] == [root["id"], second["id"], first["id"], leaf["id"]]
    assert context["path"][-1]["title"] == "a/b%"
    assert context["prompt"].endswith(f"/a%2Fb%25 [{leaf['id']}]")
    with pytest.raises(TreecerError) as error:
        service.move_node(second["id"], leaf["id"], 1)
    assert error.value.code == "INVALID_MOVE"
    assert service.get_context(second["id"])["node"]["revision"] == 1
    cleared = service.update_node(leaf["id"], 1, note="")["node"]
    assert cleared["note"] == ""
    assert cleared["title"] == "a/b%"


def test_project_and_tree_boundaries(env, tmp_path):
    make, home, _ = env
    a = make()
    a.create_task("Topic")
    a_root = a.create_tree("Project root", note="private content")["node"]
    other_tree = a.create_tree("second tree")["node"]
    with pytest.raises(TreecerError) as error:
        a.add_node("bad edge", a_root["id"], other_tree["tree_id"])
    assert error.value.code == "TREE_MISMATCH"
    with pytest.raises(TreecerError):
        a.move_node(a.add_node("child")["node"]["id"], a_root["id"], 1)
    game = tmp_path / "OtherProject"
    game.mkdir()
    b = TreeService(ContextResolver(home, game, "codex", "chat-1"))
    assert b.get_context()["tasks"] == []
    b_root = b.create_tree("Game root")["node"]
    assert a_root["id"] == b_root["id"]  # Independent project-local numbering.
    assert b.get_context(a_root["id"])["node"]["note"] == ""
    assert a.get_context(a_root["id"])["node"]["note"] == "private content"
    assert a.database != b.database
    assert make().get_context()["project"]["id"] == a.context["id"]


def test_pagination_search_and_read_does_not_focus(env):
    make, _, _ = env
    service = make()
    root = service.create_tree("root")["node"]
    children = [service.add_node("match")["node"] for _ in range(7)]
    service.add_node("grandchild", children[0]["id"])
    page = service.show_children(limit=3)
    assert [row["id"] for row in page["children"]] == [row["id"] for row in children[:3]]
    assert page["next_offset"] == 3
    page2 = service.show_children(limit=3, offset=6)
    assert len(page2["children"]) == 1 and page2["next_offset"] is None
    matches = service.find_nodes("match", limit=2)
    assert len(matches["matches"]) == 2 and matches["next_offset"] == 2
    assert matches["matches"][0]["path"][-1]["id"] == children[0]["id"]
    service.get_context(children[0]["id"])
    assert make().get_context()["node"]["id"] == root["id"]
    assert service.get_parent(root["id"])["path"] == []
    with pytest.raises(TreecerError):
        service.show_children(limit=0)


def test_task_scope_and_selection(env):
    make, _, _ = env
    service = make()
    project_tree = service.create_tree("inbox", project_level=True)["node"]
    task = service.create_task("work")["created"]
    assert service.get_context()["node"] is None
    root = service.create_tree("work discussion")["node"]
    service.create_tree("other discussion")
    assert len(service.list_trees()["trees"]) == 2
    assert len(service.list_trees(project_level=True)["trees"]) == 1
    service.focus(project_level=True)
    assert service.get_context()["task"] is None
    service.focus(task=task)
    assert service.get_context()["task"]["id"] == task
    assert service.get_context()["node"] is None
    service.focus(root["id"], task=task)
    with pytest.raises(TreecerError) as error:
        service.focus(project_tree["id"], task=task)
    assert error.value.code == "TASK_MISMATCH"
    service.create_task("work")
    with pytest.raises(TreecerError) as error:
        service.focus(task="work")
    assert error.value.code == "AMBIGUOUS_TASK"


def test_concurrent_creates_get_unique_ids(env):
    make, _, _ = env
    root = make().create_tree("root")["node"]

    def add(index):
        return make("worker", str(index)).add_node(str(index), root["id"])["node"]["id"]

    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(add, range(18)))
    assert len(set(ids)) == 18
    assert len(make().show_children(root["id"])["children"]) == 18
