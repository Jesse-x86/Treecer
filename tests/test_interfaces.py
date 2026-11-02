import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXECUTABLE = Path(sys.executable).with_name(
    "treecer.exe" if os.name == "nt" else "treecer"
)


def assert_public(value):
    if isinstance(value, dict):
        assert not any(key == "id" or key.endswith("_id") for key in value), value
        for item in value.values():
            assert_public(item)
    elif isinstance(value, list):
        for item in value:
            assert_public(item)


def cli(home, workspace, *args, check=True):
    result = subprocess.run(
        [
            str(EXECUTABLE),
            "--home",
            str(home),
            "--workspace",
            str(workspace),
            "--json",
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    if check:
        assert result.returncode == 0, result.stderr
        value = json.loads(result.stdout)
        assert_public(value)
        return value
    return result


def test_installed_cli_paths_resume_prompt_and_sudo(tmp_path):
    workspace = tmp_path / "项目 with spaces"
    workspace.mkdir()
    home = tmp_path / "data"
    assert cli(home, workspace, "context", "show")["node"] is None
    cli(home, workspace, "task", "add", "Topic")
    root = cli(home, workspace, "node", "add", "方案讨论")["node"]
    assert root["path"] == "~/方案讨论"
    cli(home, workspace, "focus", root["path"])
    child = cli(
        home, workspace, "node", "add", "选择条件", "--note", "助手建议：待确认"
    )
    assert child["prompt"] == "Topic@项目 with spaces: ~/方案讨论$"
    cli(home, workspace, "focus", child["node"]["path"])
    resumed = cli(home, workspace, "context", "show")
    assert resumed["node"]["note"] == "助手建议：待确认"
    assert resumed["prompt"] == "Topic@项目 with spaces: ~/方案讨论/选择条件$"
    revision = resumed["node"]["revision"]
    cli(
        home,
        workspace,
        "node",
        "update",
        ".",
        "--revision",
        str(revision),
        "--status",
        "已解决",
        "--note",
        "用户已确定：保留条件",
    )
    conflict = cli(
        home,
        workspace,
        "node",
        "update",
        ".",
        "--revision",
        str(revision),
        "--note",
        "stale",
        check=False,
    )
    assert (
        conflict.returncode == 1
        and json.loads(conflict.stderr)["error"] == "REVISION_CONFLICT"
    )
    cli(home, workspace, "task", "add", "OtherTopic")
    external = cli(home, workspace, "node", "add", "topic")["node"]
    cli(home, workspace, "task", "use", "Topic")
    absolute = "/项目 with spaces/OtherTopic/topic"
    read = cli(home, workspace, "node", "get", absolute)
    assert (
        read["target"]["task"] == "OtherTopic"
        and read["current"]["task"] == "Topic"
    )
    path_output = subprocess.run(
        [
            str(EXECUTABLE),
            "--home",
            str(home),
            "--workspace",
            str(workspace),
            "path",
            absolute,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert path_output.returncode == 0, path_output.stderr
    assert path_output.stdout.startswith(
        "Topic@项目 with spaces: ~/方案讨论/选择条件$"
    )
    assert "祖先：" in path_output.stdout and absolute in path_output.stdout
    denied = cli(
        home,
        workspace,
        "node",
        "update",
        absolute,
        "--revision",
        str(external["revision"]),
        "--note",
        "wrong",
        check=False,
    )
    assert denied.returncode == 1
    error = json.loads(denied.stderr)
    assert error["error"] == "SUDO_REQUIRED" and "未执行" in error["message"]
    warning = subprocess.run(
        [
            str(EXECUTABLE),
            "--home",
            str(home),
            "--workspace",
            str(workspace),
            "node",
            "update",
            absolute,
            "--revision",
            str(external["revision"]),
            "--note",
            "wrong",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert warning.returncode == 1
    assert "当前任务：Topic@项目 with spaces" in warning.stderr
    assert "目标任务：OtherTopic@项目 with spaces" in warning.stderr
    assert "目标路径：" + absolute in warning.stderr
    assert '"~/topic"' in warning.stderr and "treecer sudo" in warning.stderr
    changed = cli(
        home,
        workspace,
        "sudo",
        "node",
        "update",
        absolute,
        "--revision",
        str(external["revision"]),
        "--note",
        "confirmed",
    )
    assert changed["current"]["task"] == "Topic"
    denied_again = cli(
        home,
        workspace,
        "node",
        "update",
        absolute,
        "--revision",
        str(changed["node"]["revision"]),
        "--note",
        "not confirmed",
        check=False,
    )
    assert denied_again.returncode == 1
    flag = cli(
        home,
        workspace,
        "node",
        "update",
        absolute,
        "--revision",
        str(changed["node"]["revision"]),
        "--note",
        "flag",
        "--sudo",
    )
    assert flag["node"]["note"] == "flag"
    # Public options also work after the leaf command.
    result = subprocess.run(
        [
            str(EXECUTABLE),
            "context",
            "show",
            "--home",
            str(home),
            "--workspace",
            str(workspace),
            "--json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["current"]["path"] == "~/方案讨论/选择条件"


def test_multiple_processes_same_database(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "data"
    cli(home, workspace, "task", "add", "work")

    def add(index):
        return cli(home, workspace, "node", "add", f"child-{index}", "--parent", "~")[
            "node"
        ]["path"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(add, range(8)))
    assert len(set(paths)) == 8
    assert len(cli(home, workspace, "children")["children"]) == 8


def test_cli_auto_resume_from_subdirectory(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "data"
    cli(home, workspace, "task", "add", "work")
    cli(home, workspace, "node", "add", "topic")
    cli(home, workspace, "focus", "~/topic")
    nested = workspace / "nested"
    nested.mkdir()
    assert cli(home, nested, "context", "show")["current"]["path"] == "~/topic"


def test_real_stdio_mcp_path_contract_cross_scope_and_restart(tmp_path):
    home = tmp_path / "data"
    workspace = tmp_path / "Project"
    workspace.mkdir()
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "treecer",
            "mcp",
            "--home",
            str(home),
            "--source",
            "codex",
            "--session",
            "chat-1",
        ],
    )

    async def run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                tools = await client.list_tools()
                names = {tool.name for tool in tools.tools}
                assert {
                    "context",
                    "tasks",
                    "use_task",
                    "add_node",
                    "focus",
                    "update_node",
                    "parent",
                } <= names
                assert "trees" not in names
                assert not any(name.startswith(("doc", "manual")) for name in names)
                for tool in tools.tools:
                    schema = json.dumps(tool.inputSchema)
                    assert (
                        "node_id" not in schema
                        and "tree_id" not in schema
                        and "parent_id" not in schema
                    )

                async def call(name, **kwargs):
                    reply = await client.call_tool(name, kwargs)
                    assert not reply.isError, reply.content
                    result = reply.structuredContent or json.loads(
                        reply.content[0].text
                    )
                    assert_public(result)
                    return result

                missing = await client.call_tool("context", {})
                assert missing.isError and "CONTEXT_REQUIRED" in missing.content[0].text
                await call("context", scope={"workspace": str(workspace)})
                await call("tasks", title="Topic")
                await call("add_node", title="方案讨论")
                await call("focus", path="~/方案讨论")
                child = (await call("add_node", title="方案比较"))["node"]
                assert (await call("context"))["node"]["path"] == "~/方案讨论"
                await call("focus", path=child["path"])
                other_scope = {
                    "source": "other",
                    "session": "chat-2",
                    "workspace": str(workspace),
                }
                await call("tasks", title="OtherTopic", scope=other_scope)
                foreign = (await call("add_node", title="外部问题", scope=other_scope))[
                    "node"
                ]
                path = "/Project/OtherTopic/外部问题"
                read = await call("context", path=path)
                assert read["current"]["task"] == "Topic"
                denied = await client.call_tool(
                    "update_node",
                    {"path": path, "revision": foreign["revision"], "note": "no"},
                )
                assert denied.isError and "SUDO_REQUIRED" in denied.content[0].text
                changed = await call(
                    "update_node",
                    path=path,
                    revision=foreign["revision"],
                    note="yes",
                    sudo=True,
                )
                assert changed["current"]["task"] == "Topic"
                second_denial = await client.call_tool(
                    "update_node",
                    {
                        "path": path,
                        "revision": changed["node"]["revision"],
                        "note": "no",
                    },
                )
                assert (
                    second_denial.isError
                    and "SUDO_REQUIRED" in second_denial.content[0].text
                )
                await call(
                    "update_node",
                    path=child["path"],
                    revision=child["revision"],
                    status="暂放",
                    note="待讨论",
                )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                reply = await client.call_tool("context", {})
                assert not reply.isError
                resumed = reply.structuredContent or json.loads(reply.content[0].text)
                assert resumed["node"]["status"] == "暂放"
                assert resumed["prompt"] == "Topic@Project: ~/方案讨论/方案比较$"

    asyncio.run(asyncio.wait_for(run(), 60))
