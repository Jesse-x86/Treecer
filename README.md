# Treecer

Treecer = tree + tracer。一个通过 CLI 或 MCP 供 AI 助手维护讨论树的本地工具。

```text
Topic@Project# 方案讨论/方案比较/比较标准 [N27]
```

位置依次显示任务、项目、根到当前节点的路径及 ID。项目独立存储，任务可跨聊天接续，各来源与会话保留自己的讨论位置。助手按需读取当前节点、祖先路径与直接孩子，再记录结论、深入或回溯。

## 用 pipx 安装

需要 Python 3.11 或更新版本，以及已配置好命令路径的 [pipx](https://pipx.pypa.io/stable/)。在源码目录执行：

```text
pipx install .
```

也可以安装本地发行包：

```text
pipx install ./dist/treecer-0.1.1-py3-none-any.whl
```

安装后可以离开源码目录使用：

```text
treecer --help
treecer setup
treecer doc
treecer doc quick-start
treecer doc quick-start --en
```

当前提供本地源码与发行包安装；包索引发布尚未执行。应用升级时继续读取用户数据目录中的讨论资料。

## 随包离线手册

`treecer doc` 列出主题，`treecer doc <主题>` 输出正文；默认中文，`--en` 阅读英文。查询手册无需绑定项目，不创建数据库。

| 主题 | 内容 |
| --- | --- |
| [quick-start](src/treecer/assets/manual/zh/quick-start.md) | 安装、首次记录与接续 |
| [core-concept](src/treecer/assets/manual/zh/core-concept.md) | 项目、任务、树、节点、来源和会话 |
| [workflow](src/treecer/assets/manual/zh/workflow.md) | 分叉、结论、暂放、回溯和协作 |
| [reference](src/treecer/assets/manual/zh/reference.md) | CLI、自动绑定、MCP、数据位置与错误处理 |

正文在包资源中维护，安装时一并分发。[英文手册](src/treecer/assets/manual/en/quick-start.md)使用相同主题名。命令语法看 `--help`；`setup` 显示接入指南和随包 skill 的实际位置。

## 从一次讨论开始

在要跟踪的工作目录运行：

```text
treecer context show
treecer task add Topic
treecer tree add 方案讨论
treecer node add 选择条件 --note "待讨论：何时触发方案比较？"
```

工具自动登记项目并生成节点 ID。随后用返回的节点 ID 调用 `focus`，完成一个问题后用 `focus ..` 返回父问题，再用 `children` 找回旁枝。完整过程见 `treecer doc quick-start`。

首次使用会在工作区写入 `.treecer/project.json`。数据库默认保存在 Windows 的 `%LOCALAPPDATA%\Treecer` 或其他平台的 `~/.local/share/Treecer`，可用 `TREECER_HOME` / `--home` 覆盖。完整发现规则、备份和恢复步骤见 `treecer doc reference`。

MCP 接入使用 `treecer mcp --workspace <实际工作区> --source <来源>`；每个聊天可通过 `scope.session` 提供稳定会话标识。工具描述和参数 schema 提供调用说明，完整接入示例见操作参考。

## 开发与验证

源码开发使用本地可编辑环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m build
```

Linux/macOS 对应 `.venv/bin/python`。测试使用独立临时工作区，覆盖树操作、项目隔离、多来源位置、并发写入、实际 CLI 和 stdio MCP 子进程，以及双语文档在未绑定项目时的读取。

CLI reference: `treecer --help`.
