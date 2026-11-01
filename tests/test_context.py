import json

import pytest

from treecer.context import ContextResolver
from treecer.errors import TreecerError
from treecer.service import TreeService


def test_auto_discovery_git_subfolder_and_persistent_manual_switch(tmp_path):
    home = tmp_path / "data"
    a, b = tmp_path / "Project", tmp_path / "OtherProject"
    a.mkdir()
    b.mkdir()
    (a / ".git").mkdir()
    nested = a / "src"
    nested.mkdir()
    a_resolver = ContextResolver(home, nested, "codex", "chat")
    a_context = a_resolver.resolve()
    assert a_context["name"] == "Project"
    assert json.loads((a / ".treecer" / "project.json").read_text())["project_id"] == a_context["id"]
    a_service = TreeService(a_resolver)
    root = a_service.create_tree("a")["node"]
    b_context = ContextResolver(home, b, "other", "chat").resolve()
    # Automatic workspace changes restore each project's own saved position.
    switched = ContextResolver(home, b, "codex", "chat").resolve()
    assert switched["id"] == b_context["id"]
    assert TreeService(a_resolver).get_context()["node"]["id"] == root["id"]
    a_resolver.resolve(project=b_context["id"])
    assert ContextResolver(home, nested, "codex", "chat").resolve()["id"] == b_context["id"]
    a_resolver.reset()
    assert a_resolver.resolve()["id"] == a_context["id"]


def test_no_mcp_workdir_guess_and_resume_without_workspace(tmp_path):
    home = tmp_path / "data"
    resolver = ContextResolver(home, source="mcp", session="saved-chat")
    with pytest.raises(TreecerError) as error:
        resolver.resolve()
    assert error.value.code == "CONTEXT_REQUIRED"
    workspace = tmp_path / "project"
    workspace.mkdir()
    context = resolver.resolve(workspace=workspace)
    assert ContextResolver(home, source="mcp", session="saved-chat").resolve()["id"] == context["id"]


def test_invalid_marker_never_redirects_database(tmp_path):
    workspace = tmp_path / "project"
    marker = workspace / ".treecer"
    marker.mkdir(parents=True)
    (marker / "project.json").write_text('{"project_id":"../../wrong"}')
    with pytest.raises(TreecerError) as error:
        ContextResolver(tmp_path / "data", workspace).resolve()
    assert error.value.code == "INVALID_MARKER"


def test_duplicate_folder_names_are_distinct_projects(tmp_path):
    workspaces = [tmp_path / "a" / "work", tmp_path / "b" / "work"]
    for workspace in workspaces:
        workspace.mkdir(parents=True)
    contexts = [ContextResolver(tmp_path / "data", folder).resolve() for folder in workspaces]
    assert contexts[0]["id"] != contexts[1]["id"]
    assert [row["name"] for row in contexts] == ["work", "work-2"]
