"""Command-line adapter. All tree operations run through TreeService."""

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .context import ContextResolver
from .errors import TreecerError
from .service import STATUSES, TreeService


def parser():
    common = argparse.ArgumentParser(add_help=False)
    for flags, settings in [
        (("--home",), {"help": "用户数据目录（默认 TREECER_HOME 或本地用户目录）"}),
        (("--workspace", "-C"), {"help": "实际工作区，自动发现或登记项目"}),
        (("--project", "-p"), {"help": "显式选择并固定项目 ID 或名称"}),
        (("--source",), {"help": "接入来源，默认 cli"}),
        (("--session",), {"help": "稳定会话标识，可用 TREECER_SESSION"}),
        (("--json",), {"action": "store_true", "help": "输出结构化 JSON"}),
    ]:
        common.add_argument(*flags, default=argparse.SUPPRESS, **settings)
    root = argparse.ArgumentParser(prog="treecer", description="Treecer：局部导航与接续讨论树", parents=[common])
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)

    def command(name, help_text, parent=commands):
        return parent.add_parser(name, help=help_text, parents=[common])

    command("projects", "列出已登记项目")
    command("setup", "查看接入说明和随包 skill 位置")
    doc = command("doc", "查询随包离线手册，默认中文")
    from .documentation import TOPICS
    doc.add_argument("topic", nargs="?", choices=TOPICS, help="省略时列出主题")
    doc.add_argument("--en", action="store_true", help="读取英文手册")
    command("mcp", "启动本地 stdio MCP 服务")
    context = command("context", "查看、换绑或重置会话关联")
    choices = context.add_subparsers(dest="action", required=True)
    command("show", "查看当前位置", choices)
    use = command("use", "切换项目、任务或树", choices)
    use.add_argument("--task")
    use.add_argument("--tree", dest="tree_id")
    use.add_argument("--node", dest="node_id")
    use.add_argument("--project-level", action="store_true")
    command("reset", "清除会话固定关联并重新发现", choices)

    tasks = command("task", "任务操作").add_subparsers(dest="action", required=True)
    command("list", "列出任务", tasks)
    command("add", "创建并选中任务", tasks).add_argument("title")
    command("use", "选择任务", tasks).add_argument("task")

    trees = command("tree", "讨论树操作").add_subparsers(dest="action", required=True)
    for action in ("list", "add"):
        item = command(action, "列出讨论树" if action == "list" else "创建并进入讨论树", trees)
        item.add_argument("--task")
        item.add_argument("--project-level", action="store_true")
        if action == "add":
            item.add_argument("title")
            item.add_argument("--note", default="")

    nodes = command("node", "节点操作").add_subparsers(dest="action", required=True)
    add = command("add", "添加孩子，自动生成 ID", nodes)
    add.add_argument("title")
    add.add_argument("--parent", dest="parent_id")
    add.add_argument("--tree", dest="tree_id")
    add.add_argument("--note", default="")
    get = command("get", "读取节点、路径与直接孩子", nodes)
    get.add_argument("node_id", nargs="?")
    get.add_argument("--tree", dest="tree_id")
    update = command("update", "更新节点并检查修订冲突", nodes)
    update.add_argument("node_id")
    update.add_argument("--revision", required=True, type=int)
    update.add_argument("--title")
    update.add_argument("--status", choices=STATUSES)
    update.add_argument("--note")
    update.add_argument("--tree", dest="tree_id")
    move = command("move", "移动分支并保留 ID", nodes)
    move.add_argument("node_id")
    move.add_argument("new_parent_id")
    move.add_argument("--revision", required=True, type=int)
    move.add_argument("--tree", dest="tree_id")

    for name in ("path", "parent", "children", "focus"):
        item = command(name, {"path": "祖先路径", "parent": "父节点及路径", "children": "直接孩子",
                              "focus": "移动讨论位置，支持 .. 返回父节点"}[name])
        item.add_argument("node_id", nargs="?")
        item.add_argument("--tree", dest="tree_id")
        if name == "focus":
            item.add_argument("--task")
            item.add_argument("--project-level", action="store_true")
        if name == "children":
            item.add_argument("--limit", type=int, default=50)
            item.add_argument("--offset", type=int, default=0)
    find = command("find", "在项目或指定树中按标题查找")
    find.add_argument("query")
    find.add_argument("--tree", dest="tree_id")
    find.add_argument("--limit", type=int, default=50)
    find.add_argument("--offset", type=int, default=0)
    return root


def render(result):
    lines = [result["prompt"]] if "prompt" in result else []
    if result.get("node"):
        node = result["node"]
        lines.append(f"{node['id']} {node['title']}〔{node['status']}〕 revision={node['revision']}")
        if node["note"]:
            lines.append(node["note"])
    if "parent" in result:
        parent = result["parent"]
        lines.append(f"父节点：{parent['title']} [{parent['id']}]" if parent else "父节点：无（树根）")
    for field, label in (("projects", "项目"), ("tasks", "任务"), ("trees", "树"),
                         ("children", "子问题"), ("matches", "匹配节点")):
        if field in result:
            lines.append(label + "：")
            for item in result[field]:
                text = f"  {item['id']} {item.get('title', item.get('name'))}"
                if "status" in item:
                    text += f"〔{item['status']}〕"
                if "path" in item:
                    text += "  " + "/".join(part["title"] for part in item["path"])
                lines.append(text)
    if result.get("next_offset") is not None:
        lines.append(f"还有后续结果：--offset {result['next_offset']}")
    if not lines:
        return json.dumps(result, ensure_ascii=False, indent=2)
    return "\n".join(lines)


def main(argv=None):
    # Windows console encoding must preserve Chinese content and paths.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = vars(parser().parse_args(argv))
    home, workspace, project, source, session, as_json = (
        args.pop(key, default) for key, default in (
            ("home", None), ("workspace", None), ("project", None),
            ("source", None), ("session", None), ("json", False)))
    name, action = args.pop("command"), args.pop("action", None)
    if name == "doc":
        from .documentation import manual, render_manual
        result = manual(args["topic"], english=args["en"])
        print(json.dumps(result, ensure_ascii=False, indent=2) if as_json else render_manual(result))
        return
    if name == "setup":
        skill = Path(__file__).parent / "assets" / "skills" / "treecer" / "SKILL.md"
        print(f"Treecer {__version__}\nSkill: {skill}\n"
              "CLI 在工作目录直接运行 treecer context show，首次使用自动登记项目。\n"
              "MCP: treecer mcp --workspace <实际工作区> --source <来源>\n"
              "每个聊天通过 scope.session 提供稳定标识；工具返回的 session 可用于恢复。\n"
              "MCP 未提供工作区时，可在工具 scope.workspace 中传入。\n"
              "离线手册：treecer doc；快速开始：treecer doc quick-start（--en 阅读英文）。\n"
              "数据位置：TREECER_HOME 或 --home；查看命令：treecer --help")
        return
    if name == "mcp":
        from .mcp_server import serve
        serve(home=home, workspace=workspace, project=project, source=source or "mcp", session=session)
        return
    try:
        resolver = ContextResolver(home, workspace or os.getcwd(), source or "cli", session)
        if name == "projects":
            result = {"projects": resolver.projects()}
        elif name == "context" and action == "reset":
            resolver.reset()
            # Reset association, retain the project data and resume positions.
            result = TreeService(resolver).get_context()
        else:
            service = TreeService(resolver, project)
            methods = {
                ("context", "show"): "get_context", ("context", "use"): "focus",
                ("task", "list"): "list_tasks", ("task", "add"): "create_task",
                ("task", "use"): "focus", ("tree", "list"): "list_trees",
                ("tree", "add"): "create_tree", ("node", "get"): "get_context",
                ("node", "add"): "add_node", ("node", "update"): "update_node",
                ("node", "move"): "move_node", ("path", None): "get_path",
                ("parent", None): "get_parent", ("children", None): "show_children",
                ("focus", None): "focus", ("find", None): "find_nodes",
            }
            # Switching only the project preserves that project's saved position.
            if name == "context" and action == "use" and not any(args.values()):
                result = service.get_context()
            else:
                result = getattr(service, methods[(name, action)])(**args)
        print(json.dumps(result, ensure_ascii=False, indent=2) if as_json else render(result))
    except (TreecerError, OSError) as error:
        details = error.as_dict() if isinstance(error, TreecerError) else {"error": "IO_ERROR", "message": str(error)}
        print(json.dumps(details, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(1) from error
