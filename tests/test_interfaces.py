import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXECUTABLE = Path(sys.executable).with_name("treecer.exe" if os.name == "nt" else "treecer")


def cli(home, workspace, *args, check=True):
    result = subprocess.run(
        [str(EXECUTABLE), "--home", str(home), "--workspace", str(workspace), "--json", *args],
        text=True, encoding="utf-8", capture_output=True, timeout=30,
    )
    if check:
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    return result


def test_installed_cli_restart_and_argument_placement(tmp_path):
    workspace = tmp_path / "项目 with spaces"
    workspace.mkdir()
    home = tmp_path / "data"
    first = cli(home, workspace, "context", "show")
    assert first["node"] is None
    cli(home, workspace, "task", "add", "Topic")
    root = cli(home, workspace, "tree", "add", "方案讨论")["node"]
    child = cli(home, workspace, "node", "add", "选择条件", "--note", "助手建议：待确认")["node"]
    cli(home, workspace, "focus", child["id"])
    resumed = cli(home, workspace, "context", "show")
    assert resumed["node"]["note"] == "助手建议：待确认"
    assert resumed["prompt"] == f"Topic@项目 with spaces# 方案讨论/选择条件 [{child['id']}]"
    updated = cli(home, workspace, "node", "update", child["id"], "--revision", "1",
                  "--status", "已解决", "--note", "用户已确定：保留条件")
    assert updated["node"]["revision"] == 2
    conflict = cli(home, workspace, "node", "update", child["id"], "--revision", "1", "--note", "stale", check=False)
    assert conflict.returncode == 1
    assert json.loads(conflict.stderr)["error"] == "REVISION_CONFLICT"
    cli(home, workspace, "focus", "..")
    assert cli(home, workspace, "context", "show")["node"]["id"] == root["id"]
    # Common options work after the leaf command as well as before it.
    result = subprocess.run([str(EXECUTABLE), "context", "show", "--home", str(home),
                             "--workspace", str(workspace), "--json"],
                            text=True, encoding="utf-8", capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["node"]["id"] == root["id"]


def test_multiple_processes_same_database(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "data"
    root = cli(home, workspace, "tree", "add", "root")["node"]

    def add(index):
        return cli(home, workspace, "node", "add", f"child-{index}", "--parent", root["id"])["node"]["id"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(add, range(8)))
    assert len(set(ids)) == 8
    assert len(cli(home, workspace, "children")["children"]) == 8


def test_cli_auto_resume_from_subdirectory(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "data"
    root = cli(home, workspace, "tree", "add", "root")["node"]
    nested = workspace / "nested"
    nested.mkdir()
    assert cli(home, nested, "context", "show")["node"]["id"] == root["id"]


def test_real_stdio_mcp_roundtrip_and_restart(tmp_path):
    home = tmp_path / "data"
    workspace = tmp_path / "Project"
    workspace.mkdir()
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "treecer", "mcp", "--home", str(home), "--source", "codex", "--session", "chat-1"],
    )

    async def run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                tools = await client.list_tools()
                assert {"context", "tasks", "trees", "add_node", "focus", "update_node", "parent"} <= {
                    tool.name for tool in tools.tools}
                assert not any(tool.name.startswith(("doc", "manual")) for tool in tools.tools)

                async def call(name, **kwargs):
                    reply = await client.call_tool(name, kwargs)
                    assert not reply.isError, reply.content
                    return reply.structuredContent or json.loads(reply.content[0].text)

                # An unbound MCP process must not use its launch directory as the user's project.
                missing = await client.call_tool("context", {})
                assert missing.isError and "CONTEXT_REQUIRED" in missing.content[0].text
                context = await call("context", scope={"workspace": str(workspace)})
                project = context["project"]
                await call("tasks", title="Topic")  # Persistent automatic binding.
                root = (await call("trees", title="方案讨论"))["node"]
                child = (await call("add_node", title="方案比较"))["node"]
                await call("focus", node_id=child["id"])
                other_scope = {"source": "other", "session": "chat-2", "workspace": str(workspace)}
                other = await call("context", scope=other_scope)
                assert other["project"] == project and other["node"] is None
                await call("focus", node_id=root["id"], scope=other_scope)
                assert (await call("context"))["node"]["id"] == child["id"]
                await call("update_node", node_id=child["id"], revision=1, status="暂放", note="待讨论")
                conflict = await client.call_tool("update_node", {"node_id": child["id"], "revision": 1, "note": "stale"})
                assert conflict.isError and "REVISION_CONFLICT" in conflict.content[0].text
        # New actual server process reconnects using the same host session identity.
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                reply = await client.call_tool("context", {})
                assert not reply.isError
                resumed = reply.structuredContent or json.loads(reply.content[0].text)
                assert resumed["node"]["id"] == child["id"]
                assert resumed["node"]["status"] == "暂放"
                assert resumed["prompt"] == f"Topic@Project# 方案讨论/方案比较 [{child['id']}]"

    asyncio.run(asyncio.wait_for(run(), timeout=60))
