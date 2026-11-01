# Treecer

Treecer = tree + tracer。一个供 AI 助手通过 CLI 或 MCP 维护讨论树的本地工具。

```text
Topic@Project# 方案讨论/方案比较/比较标准 [N27]
```

依次显示任务、项目、根到当前节点的路径及节点 ID。助手可以随讨论新增分支、记录结论、回到父问题，读取当前节点和直接孩子即可继续讨论。

## 安装与试用

需要 Python 3.11 或更新版本。在源码目录安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\treecer.exe --help
```

Linux/macOS 使用 `.venv/bin/python` 与 `.venv/bin/treecer`。安装后的命令也可通过 `python -m treecer` 调用。

在工作目录首次使用时，自动登记项目、分配稳定项目 ID，写入 `.treecer/project.json`。标记保存在实际工作区；数据库保存在用户本地数据目录。项目名取自工作区目录名，同名目录登记成不同项目时自动补充名称后缀。

```powershell
.\.venv\Scripts\treecer.exe context show
.\.venv\Scripts\treecer.exe task add Topic
.\.venv\Scripts\treecer.exe tree add 方案讨论
.\.venv\Scripts\treecer.exe node add 选择条件 --note '待讨论：何时触发方案比较？'
.\.venv\Scripts\treecer.exe focus N2
.\.venv\Scripts\treecer.exe context show
.\.venv\Scripts\treecer.exe node update N2 --revision 1 --note '用户已确定：按消息需要方案比较' --status 已解决
.\.venv\Scripts\treecer.exe focus ..
.\.venv\Scripts\treecer.exe children
```

上例的 N2 假设全新项目先创建根节点 N1；实际使用以命令返回的自动 ID 为准。节点 ID 在项目内唯一，标题允许重复，改名与移动保留 ID。

首次登记前，工具向上查找项目标记、已登记工作区和 Git 根目录。在已有项目的子目录调用仍会找到同一项目。没有这些线索时，以显式工作区或 CLI 当前目录创建项目。

## 项目、任务和会话

- 每个项目一个独立数据库；任务和讨论树归属项目。
- 一项任务允许多棵树，`tree add --project-level` 创建项目级树。
- `task add` 创建并选择任务，`tree add` 创建并进入树根。
- 新会话先看到项目概览；按任务名称或 ID 选择，再选择树或节点。
- 创建孩子和普通读取保留当前位置；`focus` 保存新的讨论位置。
- 来源与会话共同标识接续位置，多个来源可共享树内容并保留各自位置。

CLI 默认以项目工作区作为会话标识；在目录间上下移动可接续同一位置。多个终端或聊天需要独立位置时传入 `--source` 和 `--session`，或设置 `TREECER_SESSION`。重新提供相同标识会恢复原位置。

```powershell
treecer context show --workspace 'V:\work\Project' --source codex --session chat-123
treecer task list
treecer task use Topic
treecer tree list
treecer focus --tree R1
```

这些示例中的裸 `treecer` 要求已激活虚拟环境或已把工具安装到可发现的位置。

手动换绑：

```powershell
treecer projects
treecer context use --project Project --task Topic
treecer context use --project game
treecer context reset
```

显式项目会固定到当前来源与会话，优先于工作目录发现。`reset` 清除该固定关联并重新根据工作区定位，保留项目数据和各项目的接续位置。自动识别到不同项目时恢复该项目自己的位置。

## 节点查询与编辑

```text
context show                  当前节点正文、祖先路径和一层孩子；未选节点时显示概览
node get [N…] --tree R…        查询指定节点，可核对所属树
path [N…]                     根到当前节点的路径
parent [N…]                   父节点和到父节点的路径
children [N…] --limit 50       直接孩子摘要，创建顺序
find 关键词 --tree R…          标题子串查找，各匹配项附路径
node add 标题 --parent N…      新增孩子并自动分配 ID
node update N… --revision 1    更新提供的 --title / --note / --status
node move N… N… --revision 1   将前一个节点及其后代移动到后一个节点下
focus N…                      保存讨论位置
focus ..                      返回父节点；在树根时保持树根
```

`--tree` 可省略。指定节点时按项目内 ID 定位；未指定节点时使用本会话当前位置。标题中的 `/` 和 `%` 在提示路径中转义，JSON 的路径数组保留原始字符和各段 ID。

状态为「讨论中、已解决、暂放、已取消」。节点正文按需记录问题目的、用户已确定、助手建议、待讨论和下一步；状态变化由显式更新决定。

更新只修改提供字段，`--note ''` 清空正文。读取返回 `revision`，更新和移动携带该值；其他调用已修改节点时返回 `REVISION_CONFLICT` 和当前内容，助手合并后重新提交。父节点需要存在，移动保持同树、单根和无环。

所有普通命令支持 `--json`，公共选项可以放在根命令或末级命令之后。孩子与搜索支持 `--limit` / `--offset`；返回 `next_offset` 表示还有后续结果。

## MCP 接入

`treecer setup` 显示接入说明和随包 skill 的实际路径。客户端按自身配置格式启动：

```json
{
  "command": "treecer",
  "args": ["mcp", "--workspace", "/absolute/path/to/project", "--source", "codex"]
}
```

这是服务器配置条目示例，放置位置和外层字段遵循所用客户端。MCP 通过 stdio 通信，日志走 stderr。

提供工具：`context`、`projects`、`tasks`、`trees`、`add_node`、`update_node`、`move_node`、`path`、`parent`、`children`、`find_nodes`、`focus`、`reset_context`。

客户端或助手可在工具参数中补充上下文：

```json
{
  "scope": {
    "workspace": "V:/work/Project",
    "source": "codex",
    "session": "host-chat-123"
  }
}
```

`scope` 的所有字段可省略；工作区来自启动参数或工具参数。首次定位后，提供相同来源与会话即可从数据库恢复项目。`scope.project` 是手动换绑入口。

服务器未收到稳定 session 时，为本连接生成会话标识并随结果返回。跨服务重启接续时，接入端或助手重新提供该标识，或使用 `--session` / `TREECER_SESSION`。多个聊天共用服务器时，每个聊天提供自己的 `scope.session`。

MCP 服务使用明确传入的实际工作区，不从服务进程启动目录猜测用户项目。没有工作区、显式项目或历史关联时返回 `CONTEXT_REQUIRED`。此时补充一次上下文即可。

## 数据位置与恢复

默认数据目录：Windows 为 `%LOCALAPPDATA%\Treecer`，其他平台为 `~/.local/share/Treecer`。`TREECER_HOME` 或 `--home` 覆盖位置。

```text
catalog.sqlite
projects/<项目ID>/project.sqlite
```

目录库保存项目名称、工作区映射及会话项目绑定；项目库保存任务、树、节点和会话位置。工作区中的 `.treecer/project.json` 保存稳定 ID。工作区标记与同一数据目录配合使用；标记所指项目未登记时明确报错。

多个本机进程可共同访问。数据库使用 WAL、外键和短事务，节点修订号处理旧正文覆盖冲突。

备份时先关闭相关 Treecer 进程，再完整复制数据目录及工作区标记；若进程异常退出留下 `-wal` / `-shm` 文件，应一并保留。恢复时将数据目录和标记放回对应位置，再运行 `context show` 核对项目与讨论位置。

## 开发和验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m build
```

测试通过独立临时工作区验证项目发现、跨项目及跨树关系、节点身份、任务选择、双来源接续、分页、冲突与并发写入。接口测试执行已安装 CLI，并通过官方 MCP 客户端启动真实 stdio 子进程、调用工具及重启接续。

CLI reference: `treecer --help`.
