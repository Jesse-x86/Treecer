from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from treecer.context import ContextResolver
from treecer.errors import TreecerError
from treecer.service import TreeService
from treecer.store import transaction


def assert_public(value):
    if isinstance(value, dict):
        assert not any(key == "id" or key.endswith("_id") for key in value), value
        for item in value.values():
            assert_public(item)
    elif isinstance(value, list):
        for item in value:
            assert_public(item)


@pytest.fixture
def env(tmp_path):
    workspace = tmp_path / "Project"
    workspace.mkdir()
    home = tmp_path / "data"

    def make(source="codex", session="chat-1", folder=workspace):
        return TreeService(ContextResolver(home, folder, source, session))

    return make, home, workspace


def ready(make):
    service = make()
    service.create_task("Topic")
    return service


def test_discussion_roundtrip_independent_sources_and_truthful_prompt(env):
    make, _, _ = env
    service = ready(make)
    added = service.add_node("方案讨论")
    assert added["prompt"] == "Topic@Project: ~$"
    assert added["node"]["path"] == "~/方案讨论"
    service.focus("~/方案讨论")
    service.add_node("方案比较", note="待讨论：如何选择方案？")
    deferred = service.add_node("压缩")
    service.update_node(
        deferred["node"]["path"], deferred["node"]["revision"], status="暂放"
    )
    service.focus("方案比较")
    leaf = service.add_node("比较标准")["node"]
    service.focus(leaf["path"])
    other = make("other", "chat-1")
    assert other.get_context()["node"] is None
    other.use_task("Topic")
    assert other.get_context()["current"]["path"] == "~"
    current = make().get_context()
    assert current["prompt"] == "Topic@Project: ~/方案讨论/方案比较/比较标准$"
    assert [part["path"] for part in current["ancestors"]] == [
        "~",
        "~/方案讨论",
        "~/方案讨论/方案比较",
        "~/方案讨论/方案比较/比较标准",
    ]
    assert_public(current)
    service.update_node(
        leaf["path"], leaf["revision"], status="已解决", note="用户已确定：保留细节"
    )
    service.focus("..")
    service.focus("..")
    children = service.show_children()["children"]
    assert [(row["title"], row["status"]) for row in children] == [
        ("方案比较", "讨论中"),
        ("压缩", "暂放"),
    ]
    assert make("other", "chat-1").get_context()["current"]["path"] == "~"


def test_name_uniqueness_and_titles_are_preserved(env):
    make, _, _ = env
    service = ready(make)
    with pytest.raises(TreecerError) as error:
        service.create_task("Topic")
    assert error.value.code == "DUPLICATE_NAME"
    service.add_node("left")
    service.add_node("right")
    first = service.add_node("same", parent="~/left")["node"]
    service.add_node("same", parent="~/right")
    with pytest.raises(TreecerError) as error:
        service.add_node("same", parent="~/left")
    assert error.value.code == "DUPLICATE_NAME"
    with pytest.raises(TreecerError):
        service.move_node(first["path"], "~/right", first["revision"])
    for title, encoded in [
        ("a/b%", "a%2Fb%25"),
        (".", "%2E"),
        ("..", "%2E%2E"),
        ("~", "%7E"),
        ("line\nbreak", "line%0Abreak"),
    ]:
        node = service.add_node(title)["node"]
        assert node["path"] == "~/" + encoded
        assert service.get_context(node["path"])["node"]["title"] == title
    assert service.get_context(first["path"])["node"]["title"] == "same"


def test_rename_move_preserve_internal_identity_and_resume(env):
    make, _, _ = env
    service = ready(make)
    source = service.add_node("branch")["node"]
    service.add_node("destination")
    leaf = service.add_node("leaf", parent=source["path"])["node"]
    identity = service.nav.locate(leaf["path"]).node["id"]
    service.focus(leaf["path"])
    renamed = service.update_node(source["path"], source["revision"], title="renamed")[
        "node"
    ]
    moved = service.move_node(renamed["path"], "~/destination", renamed["revision"])
    assert moved["prompt"] == "Topic@Project: ~/destination/renamed/leaf$"
    assert make().nav.locate().node["id"] == identity
    assert make().get_context()["node"]["title"] == "leaf"
    with pytest.raises(TreecerError) as error:
        service.move_node(
            "~/destination",
            "~/destination/renamed/leaf",
            service.get_context("~/destination")["node"]["revision"],
        )
    assert error.value.code == "INVALID_MOVE"
    assert_public(moved)


def test_stale_revision_and_reused_path_cannot_update_a_different_node(env):
    make, _, _ = env
    service = ready(make)
    first = service.add_node("a", note="original")["node"]
    service.update_node("~/a", first["revision"], title="renamed")
    replacement = service.add_node("a", note="new node")["node"]
    assert replacement["revision"] != first["revision"]
    with pytest.raises(TreecerError) as error:
        service.update_node("~/a", first["revision"], note="stale")
    assert error.value.code == "REVISION_CONFLICT"
    assert error.value.details["current"]["note"] == "new node"
    assert_public(error.value.as_dict())
    current = service.update_node("~/a", replacement["revision"], note="")["node"]
    assert current["note"] == "" and current["title"] == "a"


def test_navigation_normalizes_before_task_scope_checks(env):
    make, _, _ = env
    service = ready(make)
    service.add_node("branch")
    service.create_task("other")
    foreign = service.add_node("node")["node"]
    service.use_task("Topic")
    service.focus("~/branch")
    read = service.get_context("../../other/node")
    assert read["target"]["absolute_path"] == "/Project/other/node"
    assert read["prompt"] == "Topic@Project: ~/branch$"
    with pytest.raises(TreecerError) as error:
        service.update_node("../../other/node", foreign["revision"], note="wrong task")
    assert error.value.code == "SUDO_REQUIRED"
    assert error.value.details["current_task_candidate"] == "~/node"
    assert service.get_parent("~")["parent"]["path"] == "/Project"
    service.focus("~")
    service.focus("..")
    assert service.get_context()["current"]["path"] == "/Project"
    assert service.get_context("~/branch")["node"]["title"] == "branch"
    assert service.show_children("/")["children"][0]["path"] == "/Project"


def test_cross_task_reads_free_writes_explicit_and_override_not_sticky(env):
    make, _, _ = env
    service = ready(make)
    service.add_node("local")
    service.focus("~/local")
    service.create_task("other")
    external = service.add_node("branch")["node"]
    service.add_node("child", parent="~/branch")
    service.use_task("Topic")
    before = service.get_context()["current"]
    path = "/Project/other/branch"
    for result in [
        service.get_context(path),
        service.get_path(path),
        service.get_parent(path),
        service.show_children(path),
        service.find_nodes("child", path=path),
    ]:
        assert result["current"] == before
        assert_public(result)
    with pytest.raises(TreecerError) as error:
        service.add_node("new", parent=path)
    assert error.value.code == "SUDO_REQUIRED"
    created = service.add_node("new", parent=path, sudo=True)
    assert created["current"] == before and created["node"]["path"] == path + "/new"
    changed = service.update_node(
        path, external["revision"], note="confirmed", sudo=True
    )
    assert changed["current"] == before
    with pytest.raises(TreecerError) as error:
        service.update_node(path, changed["node"]["revision"], note="not confirmed")
    assert error.value.code == "SUDO_REQUIRED"
    with pytest.raises(TreecerError):
        service.move_node(
            "~/local", path, service.get_context("~/local")["node"]["revision"]
        )
    service.focus(path)
    assert (
        service.get_context()["prompt"] == "Topic@Project: /Project/other/branch$"
    )
    with pytest.raises(TreecerError):
        service.add_node("implicit write to foreign cwd")
    service.focus("~")
    assert service.get_context()["current"]["path"] == "~"


def test_cross_task_move_and_session_following(env):
    make, _, _ = env
    service = ready(make)
    branch = service.add_node("branch")["node"]
    service.add_node("leaf", parent=branch["path"])
    service.focus("~/branch/leaf")
    service.create_task("other")
    service.use_task("Topic")
    service.move_node("~/branch", "/Project/other", branch["revision"], sudo=True)
    current = service.get_context()
    assert current["current"]["task"] == "Topic"
    assert current["current"]["path"] == "/Project/other/branch/leaf"
    assert service.get_context("/Project/other/branch")["node"]["title"] == "branch"
    service.focus("~")
    assert service.show_children()["children"] == []


def test_cross_project_move_is_atomic_and_preserves_identity(env, tmp_path):
    make, home, _ = env
    service = ready(make)
    branch = service.add_node("branch")["node"]
    service.add_node("leaf", parent=branch["path"])
    identity = service.nav.locate("~/branch/leaf").node["id"]
    service.focus("~/branch/leaf")
    game = tmp_path / "OtherProject"
    game.mkdir()
    other = make("other", "other-chat", game)
    other.create_task("combat")
    before = other.get_context()["current"]
    service.move_node("~/branch", "/OtherProject/combat", branch["revision"], sudo=True)
    assert service.nav.locate("/OtherProject/combat/branch/leaf").node["id"] == identity
    assert service.get_context()["current"]["path"] == "/OtherProject/combat/branch/leaf"
    assert other.get_context()["current"] == before
    assert other.get_context("~/branch/leaf")["node"]["title"] == "leaf"
    assert service.get_context("~")["children"] == []
    assert service.database != other.database


def test_cross_project_failed_move_rolls_back_all_files(env, tmp_path):
    make, _, _ = env
    service = ready(make)
    node = service.add_node("branch", note="valuable")["node"]
    service.add_node("leaf", parent="~/branch")
    service.focus("~/branch/leaf")
    game = tmp_path / "OtherProject"
    game.mkdir()
    other = make("other", "chat", game)
    other.create_task("combat")
    with transaction(service.database, write=True) as (db, _):
        db.execute(
            "CREATE TRIGGER fail_move BEFORE DELETE ON nodes WHEN OLD.title='branch' BEGIN SELECT RAISE(ABORT,'injected'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        service.move_node("~/branch", "/OtherProject/combat", node["revision"], sudo=True)
    assert service.get_context("~/branch")["node"]["note"] == "valuable"
    assert service.get_context()["current"]["path"] == "~/branch/leaf"
    assert other.show_children("~")["children"] == []


def test_pagination_search_creation_order_and_concurrent_add(env):
    make, _, _ = env
    service = ready(make)
    for index in range(7):
        service.add_node(f"item-{index}")
    first = service.get_context("~/item-0")["node"]
    service.update_node(first["path"], first["revision"], note="updated")
    page = service.show_children(limit=3)
    assert [row["title"] for row in page["children"]] == ["item-0", "item-1", "item-2"]
    assert page["next_offset"] == 3
    assert service.show_children(limit=3, offset=6)["next_offset"] is None
    assert service.find_nodes("item-", limit=2)["next_offset"] == 2
    with pytest.raises(TreecerError):
        service.show_children(limit=0)

    def add(index):
        worker = make("worker", str(index))
        worker.use_task("Topic")
        return worker.add_node(f"worker-{index}")

    with ThreadPoolExecutor(max_workers=6) as pool:
        replies = list(pool.map(add, range(18)))
    assert len({row["node"]["path"] for row in replies}) == 18
    assert all(row["current"]["path"] == "~" for row in replies)
    assert len(service.show_children()["children"]) == 25
    for row in replies:
        assert_public(row)


def test_root_content_and_global_namespace(env):
    make, _, _ = env
    service = ready(make)
    root = service.get_context("~")["node"]
    changed = service.update_node("~", root["revision"], note="task purpose")
    assert changed["node"]["note"] == "task purpose"
    with pytest.raises(TreecerError):
        service.update_node("~", changed["node"]["revision"], title="new root")
    with pytest.raises(TreecerError):
        service.move_node("~", "~", changed["node"]["revision"])
    service.focus("/")
    assert service.get_parent()["parent"] is None
    assert service.get_context()["node"] is None
    service.focus("~")
    assert service.get_context()["node"]["note"] == "task purpose"


def test_unbound_reader_gets_actionable_write_warning(env):
    make, _, _ = env
    owner = ready(make)
    node = owner.add_node("topic")["node"]
    reader = make("reader", "new-chat")
    assert reader.get_context("/Project/Topic/topic")["node"]["title"] == "topic"
    with pytest.raises(TreecerError) as error:
        reader.update_node(
            "/Project/Topic/topic", node["revision"], note="unconfirmed"
        )
    assert error.value.code == "SUDO_REQUIRED"
    assert error.value.details["current_task_candidate"] is None
    assert "task use" in str(error.value)
    assert owner.get_context("~/topic")["node"]["note"] == ""
