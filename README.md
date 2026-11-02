# Treecer

**深入聊下去，也能找回原来的问题。**

和 AI 讨论一个复杂问题时，一个分支往往又引出另一个分支。聊得很深入，回头却忘了最初的问题，还有哪些想法没有聊完。

Treecer 把这些问题、结论和旁枝保存成一棵可接续的讨论树。助手可以随对话维护它，每次只读取当前位置、祖先路径和直接孩子，接着讨论。

```text
Topic@Project# 方案讨论/方案比较/比较标准 [N27]
```

这一行告诉你：正在为 **Project** 项目的 **Topic** 任务，讨论「比较标准」；往上可以回到「方案比较」和「方案讨论」。

Treecer = **tree + tracer**。它是一个本地 Python 工具，提供 CLI 和 MCP 接口，供你已有的 AI 助手调用。

## 能做什么

- **跟踪讨论分支**：记录问题、用户决定、助手建议、开放问题和下一步。
- **局部浏览与回溯**：查看路径、父问题和直接孩子，找回暂放的旁枝。
- **按项目和任务组织**：每个项目独立存储，一项任务可以有多棵讨论树。
- **跨聊天接续**：不同助手和会话共享讨论内容，分别保存自己的位置。
- **自动维护身份**：节点 ID 自动生成，标题可以重复，改名和移动保留 ID。
- **本地持久化**：使用 SQLite 保存数据；Treecer 自身不调用模型。

## 安装

需要 **Python 3.11+** 和已配置好命令路径的 [pipx](https://pipx.pypa.io/stable/)。

首个版本发布到 PyPI 后，可执行：

```text
pipx install treecer
```

当前也可以安装收到的 wheel 文件，或在源码目录安装：

```text
pipx install ./treecer-0.1.1-py3-none-any.whl
```

```text
pipx install .
```

安装完成后，进入要记录讨论的工作目录：

```text
treecer --help
treecer setup
treecer doc quick-start
```

`setup` 提供助手接入指南及随包 skill 的实际位置。

## 试一次分叉和回溯

例如，在一个名为 Project 的工作区中：

```text
treecer context show
treecer task add Topic
treecer tree add 方案讨论
treecer node add 方案选择 --note "待讨论：如何选择合适的方案？"
```

工具自动发现或登记项目，创建任务、树和节点，并返回生成的 ID。

假设新问题返回 `N2`，可以进入它：

```text
treecer focus N2
treecer context show
```

```text
Topic@Project# 方案讨论/方案选择 [N2]
N2 方案选择〔讨论中〕 revision=1
待讨论：如何选择合适的方案？
子问题：
```

讨论告一段落后，用读取到的修订号记录结论，回到父问题：

```text
treecer node update N2 --revision 1 --status 已解决 --note "用户已确定：按实际使用场景比较方案"
treecer focus ..
treecer children
```

实际操作使用工具返回的 ID 和 revision。普通读取和新增孩子保留当前位置；`focus` 保存新的讨论位置。重新进入同一会话后，可以从该位置接续。

## 和 AI 助手一起使用

### CLI

支持终端调用的助手可以直接运行 `treecer`。可以这样交代它：

> 用 Treecer 跟踪这次讨论。先查看当前项目和位置；出现有价值的分支、确认结论或切换话题时更新。聊完一个分支后，帮我回到父问题并找回还没聊完的旁枝。

`treecer setup` 会显示随包 skill 的位置。这个 skill 指导助手怎样分叉、记录和回溯；命令详情可以按需查阅离线手册。

### MCP

在支持 stdio MCP 的客户端中，按客户端的配置格式添加服务器条目：

```json
{
  "command": "treecer",
  "args": ["mcp", "--workspace", "/absolute/path/to/project", "--source", "my-assistant"]
}
```

`command` 使用客户端能够找到的可执行文件，也可以填写其绝对路径。`--workspace` 填实际工作区。

多个聊天共用入口时，助手或接入端通过工具参数提供各自稳定的会话标识：

```json
{
  "scope": {
    "session": "chat-123"
  }
}
```

相同来源与会话可以在重启后接续。工具也会返回当前 session；完整接入方式见 `treecer doc reference`。

## 随包离线手册

```text
treecer doc
treecer doc quick-start
treecer doc core-concept
treecer doc workflow
treecer doc reference
```

默认中文，添加 `--en` 阅读英文：

```text
treecer doc quick-start --en
```

| 主题 | 内容 |
| --- | --- |
| quick-start | 安装、首次记录和接续 |
| core-concept | 项目、任务、树、节点、来源与会话 |
| workflow | 分叉、结论、暂放、回溯与协作 |
| reference | CLI、自动绑定、MCP、数据位置和排障 |

手册随安装包分发，读取时无需绑定项目。命令语法用 `--help` 查询。

## 数据保存在哪里

首次登记项目时，在工作区写入 `.treecer/project.json` 保存项目身份。数据库默认保存在：

| 平台 | 默认数据目录 |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Treecer` |
| Linux / macOS | `~/.local/share/Treecer` |

可以用 `TREECER_HOME` 或 `--home` 指定数据目录。升级程序后继续读取原有讨论资料。

CLI 默认按工作区接续；需要区分聊天或终端时，使用 `--source`、`--session` 或 `TREECER_SESSION`。换绑、备份和恢复步骤见 `treecer doc reference`。

## 开发

```text
python -m venv .venv
```

激活虚拟环境后：

```text
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

当前验收环境为 Windows / Python 3.12，包含实际 CLI、多进程写入和 stdio MCP 接续测试。安装包也经过独立 pipx 安装及离开源码目录后的调用验证。

## 许可证

MIT。
