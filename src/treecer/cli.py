"""Path-based command line. The sudo prefix confirms one cross-task write."""

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .context import ContextResolver
from .documentation import TOPICS, manual, render_manual
from .errors import TreecerError
from .service import STATUSES, TreeService


def parser():
    common = argparse.ArgumentParser(add_help=False)
    for flags, settings in [
        (("--home",), {"help": "用户数据目录；默认 TREECER_HOME 或本地用户目录"}),
        (("--workspace", "-C"), {"help": "实际工作区，自动发现项目"}),
        (("--project", "-p"), {"help": "手动选择并固定项目名称"}),
        (("--source",), {"help": "接入来源；默认 cli"}),
        (("--session",), {"help": "稳定会话标识；可用 TREECER_SESSION"}),
        (("--json",), {"action": "store_true", "help": "结构化输出"}),
        (("--sudo",), {"action": "store_true", "help": "显式确认本次跨任务写入"}),
    ]:
        common.add_argument(*flags, default=argparse.SUPPRESS, **settings)
    root = argparse.ArgumentParser(
        prog="treecer",
        description="Treecer：用路径接续讨论树",
        parents=[common],
        epilog='跨任务写入：treecer sudo node update "/项目/任务/节点" ...；~ 表示当前任务根。',
    )
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)

    def command(name, description, parent=commands):
        return parent.add_parser(name, help=description, parents=[common])

    command("projects", "列出已登记项目")
    command("setup", "查看接入指南和随包 skill 位置")
    command("mcp", "启动 stdio MCP 服务")
    doc = command("doc", "随包手册：默认中文，--en 英文")
    doc.add_argument("topic", nargs="?", choices=TOPICS)
    doc.add_argument("--en", action="store_true")
    context = command("context", "查看上下文或手动换绑")
    actions = context.add_subparsers(dest="action", required=True)
    show = command("show", "查看当前位置或指定路径", actions)
    show.add_argument("path", nargs="?")
    show.add_argument("--limit", type=int, default=50)
    show.add_argument("--offset", type=int, default=0)
    use = command("use", "固定项目，选择任务或位置", actions)
    use.add_argument("--task")
    use.add_argument("--path")
    command("reset", "清除项目固定关联并重新发现", actions)
    tasks = command("task", "任务操作").add_subparsers(dest="action", required=True)
    listing = command("list", "按名称列出任务", tasks)
    listing.add_argument("--at", dest="project_path", help="项目路径，如 /Project")
    command("add", "创建任务并进入 ~", tasks).add_argument("title")
    command("use", "按名称选择任务，恢复位置", tasks).add_argument("title")
    nodes = command("node", "讨论节点操作").add_subparsers(dest="action", required=True)
    add = command("add", "在当前或指定父节点下新增", nodes)
    add.add_argument("title")
    add.add_argument("--parent")
    add.add_argument("--note", default="")
    get = command("get", "读取正文、祖先和直接孩子", nodes)
    get.add_argument("path", nargs="?")
    get.add_argument("--limit", type=int, default=50)
    get.add_argument("--offset", type=int, default=0)
    update = command("update", "更新路径指向的节点", nodes)
    update.add_argument("path")
    update.add_argument("--revision", type=int, required=True)
    update.add_argument("--title")
    update.add_argument("--note")
    update.add_argument("--status", choices=STATUSES)
    move = command("move", "移动分支到指定父路径", nodes)
    move.add_argument("path")
    move.add_argument("new_parent")
    move.add_argument("--revision", type=int, required=True)
    for name, description in (
        ("path", "祖先路径"),
        ("parent", "父节点及路径"),
        ("children", "直接孩子"),
        ("focus", "保存讨论位置；支持 ~ 和 .."),
    ):
        item = command(name, description)
        item.add_argument("path", nargs="?", default="~" if name == "focus" else None)
        if name == "children":
            item.add_argument("--limit", type=int, default=50)
            item.add_argument("--offset", type=int, default=0)
    find = command("find", "按标题子串查找，默认当前任务")
    find.add_argument("query")
    find.add_argument("--at", dest="path")
    find.add_argument("--limit", type=int, default=50)
    find.add_argument("--offset", type=int, default=0)
    return root


def render(result):
    lines = [result["prompt"]] if "prompt" in result else []
    if (
        result.get("target")
        and result.get("current")
        and not result.get("node")
        and result["target"]["absolute_path"] != result["current"]["absolute_path"]
    ):
        lines.append("目标：" + result["target"]["path"])
    if result.get("node"):
        node = result["node"]
        action = {"add": "已添加", "update": "已更新", "move": "已移动"}.get(
            result.get("operation"), "节点"
        )
        lines.append(
            f"{action}：{node['path']}〔{node['status']}〕 revision={node['revision']}"
        )
        if node["note"]:
            lines.append(node["note"])
    if "parent" in result:
        parent = result["parent"]
        lines.append(f"父节点：{parent['path']}" if parent else "父节点：无")
    if "ancestors" in result and "node" not in result and "parent" not in result:
        lines.append(
            "祖先：" + " → ".join(item["path"] for item in result["ancestors"])
        )
    for field, label in (
        ("projects", "项目"),
        ("tasks", "任务"),
        ("children", "子问题"),
        ("matches", "匹配节点"),
    ):
        if field in result:
            lines.append(label + "：")
            for item in result[field]:
                line = f"  {item['title']}  {item['path']}"
                if "status" in item:
                    line += f"〔{item['status']}〕"
                lines.append(line)
    if result.get("next_offset") is not None:
        lines.append(f"还有后续结果：--offset {result['next_offset']}")
    return (
        "\n".join(lines) if lines else json.dumps(result, ensure_ascii=False, indent=2)
    )


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    arguments = list(sys.argv[1:] if argv is None else argv)
    index = 0
    value_options = {
        "--home",
        "--workspace",
        "-C",
        "--project",
        "-p",
        "--source",
        "--session",
    }
    while index < len(arguments):
        token = arguments[index]
        if token in value_options:
            index += 2
        elif token in ("--json", "--sudo") or any(
            token.startswith(flag + "=")
            for flag in value_options
            if flag.startswith("--")
        ):
            index += 1
        elif (token.startswith("-C") or token.startswith("-p")) and len(token) > 2:
            index += 1
        else:
            break
    prefix_sudo = index < len(arguments) and arguments[index] == "sudo"
    if prefix_sudo:
        arguments.pop(index)
    args = vars(parser().parse_args(arguments))
    home, workspace, project, source, session, as_json, sudo = (
        args.pop(key, default)
        for key, default in (
            ("home", None),
            ("workspace", None),
            ("project", None),
            ("source", None),
            ("session", None),
            ("json", False),
            ("sudo", False),
        )
    )
    sudo = sudo or prefix_sudo
    name, action = args.pop("command"), args.pop("action", None)
    if name == "doc":
        result = manual(args["topic"], english=args["en"])
        print(
            json.dumps(result, ensure_ascii=False, indent=2)
            if as_json
            else render_manual(result)
        )
        return
    if name == "setup":
        skill = Path(__file__).parent / "assets/skills/treecer/SKILL.md"
        print(
            f"Treecer {__version__}\nSkill: {skill}\n"
            "CLI: treecer context show；task add/use 选择任务，~ 指向任务根。\n"
            "MCP: treecer mcp --workspace <实际工作区> --source <来源>\n"
            "每个聊天用 scope.session 提供稳定标识，工具返回的 session 可用于接续。\n"
            "跨任务查看直接允许；写入用 treecer sudo <原指令> 或 MCP sudo=true。\n"
            "离线手册：treecer doc quick-start（--en 英文）；参数：treecer --help"
        )
        return
    if name == "mcp":
        from .mcp_server import serve

        serve(
            home=home,
            workspace=workspace,
            project=project,
            source=source or "mcp",
            session=session,
        )
        return
    try:
        resolver = ContextResolver(
            home, workspace or os.getcwd(), source or "cli", session
        )
        if name == "projects":
            result = {"projects": resolver.projects()}
        else:
            if name == "context" and action == "reset":
                resolver.reset()
                project = None
            service = TreeService(resolver, project)
            methods = {
                ("context", "show"): "get_context",
                ("context", "reset"): "get_context",
                ("task", "list"): "list_tasks",
                ("task", "add"): "create_task",
                ("task", "use"): "use_task",
                ("node", "get"): "get_context",
                ("node", "add"): "add_node",
                ("node", "update"): "update_node",
                ("node", "move"): "move_node",
                ("path", None): "get_path",
                ("parent", None): "get_parent",
                ("children", None): "show_children",
                ("focus", None): "focus",
                ("find", None): "find_nodes",
            }
            if name == "context" and action == "use":
                if args["task"]:
                    service.use_task(args["task"])
                result = (
                    service.focus(args["path"])
                    if args["path"]
                    else service.get_context()
                )
            else:
                method = methods[(name, action)]
                if method in ("add_node", "update_node", "move_node"):
                    args["sudo"] = sudo
                result = getattr(service, method)(**args)
        print(
            json.dumps(result, ensure_ascii=False, indent=2)
            if as_json
            else render(result)
        )
    except (TreecerError, OSError) as error:
        details = (
            error.as_dict()
            if isinstance(error, TreecerError)
            else {"error": "IO_ERROR", "message": str(error)}
        )
        if not as_json and details["error"] == "SUDO_REQUIRED":
            target = details["target"]
            lines = [
                "SUDO_REQUIRED：本次修改未执行。",
                "当前任务：" + details["current_task"],
                f"目标任务：{target['task']}@{target['project']}",
                "目标路径：" + target["absolute_path"],
                "确认目标后，请使用 treecer sudo 重试原指令。",
            ]
            candidate = details.get("current_task_candidate")
            lines.append(
                f'若本意是当前任务，请核对 "{candidate}" 并修正指令。'
                if candidate
                else "当前尚未选择任务，也可先用 task use 选择目标任务。"
            )
            print("\n".join(lines), file=sys.stderr)
        else:
            print(json.dumps(details, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(1) from error
