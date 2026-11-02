# Treecer

**深入聊下去，也能找回原来的问题。**

和 AI 讨论一个复杂问题时，一个分支往往又引出另一个分支。聊得很深入，回头却忘了最初的问题，还有哪些想法没有聊完。

Treecer 把问题、结论和旁枝保存成可接续的讨论树。助手随对话维护它，每次按需读取当前位置、祖先和直接孩子，再深入或回溯。

```text
Topic@Project: ~/方案讨论/方案选择$
```

这一行表示：当前绑定 Project 项目的 Topic 任务，正在讨论「方案讨论」下的「方案选择」。~ 是任务根，对应 `/Project/Topic`。

Treecer = **tree + tracer**。这是一个本地 Python 工具，通过 CLI 和 MCP 供你已有的助手调用。

## 能做什么

- **按路径维护讨论**：同父名称唯一，节点身份由工具内部维护，改名和移动后会话位置跟随。
- **局部浏览与回溯**：查看正文、祖先和直接孩子，找回暂放的旁枝。
- **按项目和任务组织**：项目分库，每项任务拥有一棵根为 ~ 的树。
- **跨聊天接续**：来源和会话共享讨论内容，分别保留任务选择和位置。
- **明确跨任务目标**：查看其他任务直接允许；修改其他任务时显式 sudo，返回准确目标归属。
- **本地持久化**：SQLite 保存数据，Treecer 自身不调用模型。

## 安装

需要 **Python 3.11+** 和已配置命令路径的 [pipx](https://pipx.pypa.io/stable/)。首个版本发布到 PyPI 后可执行：

```text
pipx install treecer
```

wheel 和源码压缩包作为 GitHub Release 附件分发，仓库只保存源码和文档。下载 Release 中的 wheel 后，可从文件安装：

```text
pipx install ./treecer-0.1.2-py3-none-any.whl
```

也可在源码目录安装：

```text
pipx install .
```

安装后进入要跟踪讨论的工作区：

```text
treecer --help
treecer setup
treecer doc quick-start
```

setup 提供助手接入指南及随包 skill 的位置。

## 试一次分叉和回溯

例如，在名为 Project 的工作目录：

```text
treecer context show
treecer task add Topic
treecer node add 方案讨论
treecer focus "~/方案讨论"
treecer node add 方案选择 --note "待讨论：如何选择合适的方案？"
```

新增返回新节点路径，同时保留当前讨论位置。明确进入它：

```text
treecer focus "~/方案讨论/方案选择"
treecer context show
```

```text
Topic@Project: ~/方案讨论/方案选择$
节点：~/方案讨论/方案选择〔讨论中〕 revision=3
待讨论：如何选择合适的方案？
子问题：
```

这里的 revision=3 对应全新示例项目；实际使用读取到的修订号。讨论结束后记录结论，再回父问题：

```text
treecer node update "~/方案讨论/方案选择" --revision 3 --status 已解决 --note "用户已确定：按实际使用场景比较方案"
treecer focus ..
treecer children
```

prompt 始终表示实际保存的位置，target 和 node 单独表示本次操作对象。路径支持 ~、相对位置、.、.. 和 `/项目/任务/节点` 绝对地址。CLI 中给 "~/..." 加引号，避免 shell 提前展开到电脑的用户目录。

## 查阅和修改其他任务

目标路径存在时，可以直接查看：

```text
treecer context show "/Project/OtherTopic/方案讨论"
```

查看保留当前绑定与位置。跨任务写入缺少 sudo 时，工具停止并提示：

```text
SUDO_REQUIRED：本次修改未执行。
当前任务：Topic@Project
目标任务：OtherTopic@Project
目标路径：/Project/OtherTopic/方案讨论
确认目标后，请使用 treecer sudo 重试原指令。
若本意是当前任务，请核对 "~/方案讨论" 并修正指令。
```

核对目标后，使用 `treecer sudo <原指令>` 或 --sudo；MCP 对应本次请求的 sudo=true。覆写逐次检查，保留当前绑定。分支移动支持跨任务与跨项目，并让保存的位置跟随节点。

## 与 AI 助手配合

### CLI

支持终端调用的助手可以直接执行 treecer。可以这样交代：

> 用 Treecer 跟踪这次讨论。先查看项目、任务和当前位置；有价值的分支、确认的结论或话题切换出现时更新。聊完一支，帮我回到父问题并找回未完成的旁枝。

`treecer setup` 给出随包 skill 的实际位置。skill 指导助手怎样记录和回溯，命令详情从离线手册按需查询。

### MCP

按客户端配置格式添加服务器条目：

```json
{
  "command": "treecer",
  "args": ["mcp", "--workspace", "/absolute/path/to/project", "--source", "my-assistant"]
}
```

command 使用客户端能找到的可执行文件或其绝对路径。--workspace 指向实际工作区。每个聊天通过工具参数提供稳定会话：

```json
{
  "scope": {
    "session": "chat-123"
  }
}
```

任务用 tasks 创建、use_task 按名称选择；context 读取上下文，add_node、update_node、move_node 使用路径。不同聊天共享内容、位置独立，相同来源与会话在重启后接续。完整参数见 `treecer doc reference`。

## 离线手册

```text
treecer doc
treecer doc quick-start
treecer doc core-concept
treecer doc workflow
treecer doc reference
treecer doc quick-start --en
```

默认中文，--en 阅读英文。四篇手册覆盖快速开始、概念、讨论方法和操作参考，随包安装；查询文档无需项目绑定。参数语法用 --help 查看。

## 数据和升级

首次登记项目会在工作区写入 `.treecer/project.json` 保存项目身份。数据库默认位于 Windows 的 `%LOCALAPPDATA%\Treecer` 或其他平台的 `~/.local/share/Treecer`，可用 TREECER_HOME 或 --home 覆盖。

CLI 默认按工作区接续；用 --source、--session 或 TREECER_SESSION 区分聊天。task use 恢复各任务自己的位置，context use 提供手动换绑。

0.1.2 首次访问时迁移旧版数据：原树根成为任务根下的主题，正文、状态和位置保留。旧项目级主题进入 inbox 任务。遇到旧数据同名冲突时，迁移回滚并报告冲突，原内容保留。升级前结束旧版服务进程，详细编码、迁移与恢复方法见操作参考。

## 开发

```text
python -m venv .venv
```

激活虚拟环境后：

```text
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build --outdir dist/pypi
```

验收覆盖路径、任务边界、并发与跨项目移动回滚、旧数据迁移、实际 CLI 和 stdio MCP 接续。当前本机验收环境为 Windows / Python 3.12。

## 许可证

MIT。
