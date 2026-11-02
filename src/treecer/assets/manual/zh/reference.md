# 操作参考

## CLI 入口与公共参数

```text
treecer --help
treecer --version
treecer setup
treecer doc
treecer doc quick-start
treecer doc core-concept --en
```

`doc` 的主题为 `quick-start`、`core-concept`、`workflow`、`reference`。省略主题列出目录，默认中文，`--en` 选择英文。`doc --json` 返回目录结构，`doc <主题> --json` 返回语言、主题、标题和正文。手册随当前安装版本分发，查询无需初始化项目。

公共参数可放在根命令或末级命令之后：

| 参数 | 用途 |
| --- | --- |
| `--home` | Treecer 用户数据目录，覆盖 `TREECER_HOME` 与默认目录 |
| `--workspace` / `-C` | 实际工作区；CLI 默认当前工作目录 |
| `--project` / `-p` | 按 ID 或唯一名称显式选择并固定项目 |
| `--source` | 接入来源，CLI 默认 cli |
| `--session` | 稳定会话标识，优先于 `TREECER_SESSION` |
| `--json` | 数据命令及 doc 的结构化输出 |

`setup` 输出接入指南与 skill 位置；`mcp` 启动 stdio 协议服务。

## 项目、任务和树

```text
treecer projects
treecer context show
treecer context use --project Project
treecer context use --project Project --task Topic
treecer context reset
treecer task list
treecer task add Topic
treecer task use T1
treecer tree list
treecer tree list --task T1
treecer tree add 方案讨论 --task T1 --note "问题与目的：……"
treecer tree add 项目灵感 --project-level
treecer focus --tree R1
treecer focus --task T1
treecer focus --project-level
```

任务可用 ID 或唯一的完整标题选择。同名任务返回匹配项，使用 ID 区分。`task add` 选择新任务；`tree add` 进入新树根。`focus --task` 选择任务并进入任务概览，`focus --project-level` 进入项目级概览。`tree list` 默认列当前任务的树，`--project-level` 列项目级树。

项目定位依次采用：显式项目、手动固定的会话绑定、实际工作区发现、缺少工作区时的历史会话绑定。自动发现从工作区向上查找项目标记或路径登记，遇到 Git 根目录时使用该工作区；没有线索则登记新项目。同名工作区会得到带后缀的不同项目名。

显式 `--project` 会固定该来源与会话的项目，随后优先使用固定关联；`context reset` 清除该关联并重新发现，保留项目内容和各项目的位置。

## 节点和局部导航

```text
treecer node get N27 --tree R1
treecer context show
treecer path N27
treecer parent N27
treecer children N27 --limit 20 --offset 0
treecer find 方案比较 --tree R1 --limit 20 --offset 0
treecer node add 比较标准 --parent N27 --note "待讨论：……"
treecer node update N28 --revision 1 --title 候选排序 --status 暂放 --note "返回条件：……"
treecer node move N28 N30 --revision 2
treecer focus N28
treecer focus ..
```

示例 ID 和修订号按实际返回值填写。指定节点时使用项目内 ID，`--tree` 可核对归属；省略节点时使用本会话位置。只指定树时读取其根节点。根节点的父路径为空，`focus ..` 在树根保持原位置。

普通读取与新增孩子保留焦点。`context show` 和 `node get` 返回当前正文、祖先路径与一层孩子；`children` 只返回直接孩子的 ID、标题、状态。分页默认 50 项，`limit` 为正数、`offset` 非负，`next_offset` 非空时有下一页。标题查找按文字子串匹配，返回各项路径。

状态参数为「讨论中、已解决、暂放、已取消」。更新只修改提供的字段，`--note ''` 清空正文。读取返回 `revision`，更新和移动必须携带；冲突时返回 `REVISION_CONFLICT` 和当前节点，合并后再提交。移动保留分支全部节点 ID，保持同树、单根和无环。

提示路径对 `/`、`%` 和换行转义，JSON 路径保留原始标题和各段 ID。名称用于显示，ID 用于定位。

## MCP 接入

按客户端格式配置以下服务器条目。`command` 使用客户端能找到的 treecer 可执行文件或其绝对路径：

```json
{
  "command": "treecer",
  "args": ["mcp", "--workspace", "V:/work/Project", "--source", "codex"]
}
```

启动参数沿用公共参数，MCP 通过 stdio 通信，日志走 stderr。服务说明、工具描述和参数 schema 指导助手调用。

工具为 `context`、`projects`、`tasks`、`trees`、`add_node`、`update_node`、`move_node`、`path`、`parent`、`children`、`find_nodes`、`focus`、`reset_context`。

- `tasks` 省略 title 列任务，提供 title 创建并选择任务。
- `trees` 省略 title 列树，提供 title 创建并进入树；task 选择任务，project_level 选择项目级树。
- `context` 返回概览或节点上下文；`add_node` 默认在当前节点下新增。
- `update_node` / `move_node` 携带读取到的 revision；字段和效果与 CLI 对应。
- `focus` 保存位置，node_id 可以为 `..`。`reset_context` 清除会话项目关联，下一次调用重新发现。

工具的 scope 可以补充实际工作区与聊天身份：

```json
{
  "scope": {
    "workspace": "V:/work/Project",
    "source": "codex",
    "session": "host-chat-123"
  }
}
```

scope 字段均可省略；workspace 来自启动或工具参数，project 是手动固定项目的入口。首次定位后，相同来源和会话可以按历史绑定恢复。每个聊天保持自己的 session；服务生成的默认 session 随结果返回，跨重启时重新提供它，或使用 `--session` / `TREECER_SESSION`。

MCP 根据明确的实际工作区定位，缺少工作区、显式项目与历史绑定时返回 `CONTEXT_REQUIRED`，补充一次 scope 即可继续。

## 数据位置、备份和错误

默认数据目录为 Windows 的 `%LOCALAPPDATA%\Treecer`，其他平台的 `~/.local/share/Treecer`；`TREECER_HOME` 或 `--home` 可覆盖。目录包含：

```text
catalog.sqlite
projects/<项目ID>/project.sqlite
```

catalog 保存项目、工作区和会话项目关联；各项目库保存任务、树、节点与位置。工作区的 `.treecer/project.json` 与同一数据目录配合使用。多个本机进程通过 WAL、外键和短事务共同访问，节点修订号检查过期编辑。

备份时关闭相关 Treecer 进程，完整复制数据目录和工作区标记；异常退出留下的 `-wal` / `-shm` 文件一并保留。恢复对应文件后，用 `context show` 核对项目与位置。

| 错误 | 处理 |
| --- | --- |
| `CONTEXT_REQUIRED` | 提供实际工作区或已登记项目 |
| `PROJECT_NOT_FOUND` | 核对项目选择、数据目录和工作区标记是否来自同一套数据 |
| `INVALID_MARKER` / `PROJECT_MISMATCH` | 核对项目标记或数据库身份，恢复正确文件 |
| `NODE_REQUIRED` | 选择节点、选择树或创建树 |
| `NODE_NOT_FOUND` / `TREE_NOT_FOUND` / `TASK_NOT_FOUND` | 在当前项目中查询实际 ID |
| `AMBIGUOUS_TASK` | 使用返回匹配项中的任务 ID |
| `TREE_MISMATCH` / `TASK_MISMATCH` | 核对节点、树和任务归属 |
| `INVALID_MOVE` | 选择同树内有效父节点，保持根与无环关系 |
| `REVISION_CONFLICT` | 合并 current 中的最新内容，使用最新 revision 提交 |
| `STORE_BUSY` / `WORKSPACE_CHANGED` | 稍后重新调用；重新读取所需上下文 |

CLI 操作失败时输出错误并返回非零退出码；MCP 返回工具错误。未知文档主题由命令帮助列出可用名称。
