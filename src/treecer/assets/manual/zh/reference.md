# 操作参考

## 入口和公共参数

```text
treecer --help
treecer --version
treecer setup
treecer doc
treecer doc quick-start --en
```

手册主题为 quick-start、core-concept、workflow、reference。doc 省略主题列目录，默认中文，--en 选英文；--json 返回结构化目录或正文。读取手册无需项目绑定。

| 参数 | 用途 |
| --- | --- |
| --home | 数据目录，覆盖 TREECER_HOME 与默认目录 |
| --workspace / -C | 实际工作区，CLI 默认工作目录 |
| --project / -p | 手动按名称选择并固定项目 |
| --source | 来源，CLI 默认 cli |
| --session | 稳定聊天标识，优先于 TREECER_SESSION |
| --json | 结构化输出 |
| --sudo | 确认本次跨任务写入，也可用 treecer sudo 前缀 |

公共参数可以放在根命令或末级命令之后。shell 中将 "~/..." 加引号，保持 Treecer 的任务根语义。

## 项目与任务

```text
treecer projects
treecer context show
treecer context use --project Project --task Topic
treecer context reset
treecer task list
treecer task list --at "/OtherProject"
treecer task add Topic
treecer task use Topic
```

task add 创建任务及根节点，并选中新任务；task use 按唯一名称选择任务，恢复该任务的位置。每个任务就是一棵树，各讨论主题用 node add 创建。

项目解析依次使用显式项目、固定会话关联、实际工作区发现、缺少工作区时的历史绑定。发现时向上查找 .treecer/project.json 或已登记路径，遇到 Git 根目录时使用该工作区；没有线索则自动登记。同名工作区得到带后缀的不同项目名。

context reset 清除项目固定关联并重新发现，保留数据、任务选择和位置。项目名称与同项目任务名称唯一，按原字符和大小写匹配。

## 路径、读取和导航

```text
treecer context show "~/方案讨论"
treecer node get "~/方案讨论/方案比较"
treecer path "~/方案讨论/方案比较"
treecer parent "~/方案讨论/方案比较"
treecer children "~" --limit 20 --offset 0
treecer find 方案比较 --at "/Project/Topic" --limit 20
treecer focus "~/方案讨论/方案比较"
treecer focus ..
treecer focus "~"
```

~ 指向当前绑定任务的根；绝对地址是 /项目/任务/节点；相对路径从当前位置解析。/ 列项目，/项目 列任务。任务根的父位置是项目目录，绝对根的父位置为空。

读取返回 prompt、current、target、source、session，以及节点、祖先或孩子等操作数据。prompt 始终显示保存的真实位置，current 的 project/task 表示当前绑定；target 表示本次对象归属。node 包含 title、path、absolute_path、parent、note、status、revision，内部 ID 留在存储层。

单次查看保留位置。focus 明确移动位置，跨任务 focus 保留原任务绑定，外部位置以绝对路径显示。读取外部节点、列孩子、查父节点和搜索均可直接执行。

孩子按创建顺序列出，更新正文保留顺序。默认每页 50 项，limit 为正数，offset 非负。next_offset 非空表示还有后续页。find 按标题文字子串查找，默认当前任务，可用 --at 选择子树、项目或全局范围。

## 新增、更新与移动

```text
treecer node add 方案讨论 --parent "~"
treecer node add 方案比较 --parent "~/方案讨论" --note "待讨论：……"
treecer node update "~/方案讨论/方案比较" --revision 3 --title 方案选择 --status 暂放 --note "返回条件：……"
treecer node move "~/方案讨论/方案选择" "~/其他主题" --revision 4
```

修订号以实际读取结果为准。新增和普通更新保持位置；改名与移动保留内部身份，会话位置跟随新路径。同父节点下名称唯一，不同分支可以同名；名称含斜杠、百分号、换行或完整名称 .、..、~ 时按 core-concept 的路径段规则编码。

更新只改提供字段，--note '' 清空正文。状态为「讨论中、已解决、暂放、已取消」。任务根可以更新正文和状态；其位置和根名称由任务身份确定。移动检查名称冲突与无环关系，支持跨任务、跨项目的整条分支移动。

跨任务写入未提供 sudo 时返回 SUDO_REQUIRED，指出当前任务、目标归属、目标路径及本任务候选路径。确认后重试原指令：

```text
treecer sudo node update "/Project/OtherTopic/方案讨论" --revision 5 --note "已核对目标"
```

该次覆写保留绑定和所选节点；若移动了所选节点，位置随节点显示新路径。后续请求重新检查。移动检查来源和目的地两端的任务归属。显式 task use / context use 用于换绑，focus 用于导航。

## MCP

按客户端配置格式添加：

```json
{
  "command": "treecer",
  "args": ["mcp", "--workspace", "/absolute/path/to/project", "--source", "my-assistant"]
}
```

command 可填客户端能找到的可执行文件或绝对路径。服务通过 stdio 通信，日志走 stderr。工具包括 context、projects、tasks、use_task、add_node、update_node、move_node、path、parent、children、find_nodes、focus、reset_context。

- context(path?) 返回上下文；path、parent、children 和 find_nodes 也使用路径。
- tasks 省略 title 列任务，提供 title 创建任务；use_task(title) 按名称换绑。
- add_node(title,parent?,note?,sudo?) 新增孩子；update_node(path,revision,...) 更新字段。
- move_node(path,new_parent,revision,sudo?) 移动分支；跨任务写请求显式 sudo=true。
- focus(path) 保存当前位置；reset_context 清除项目固定关联。

工具 scope 可提供 workspace、project 名称、source 和 session。每个聊天使用自己的稳定 session；未提供时服务器生成并返回一个，跨重启时重新提供。MCP 不从服务启动目录推测实际工作区；没有工作区、显式项目或历史绑定时返回 CONTEXT_REQUIRED。

## 数据和升级

默认数据目录：Windows 为 %LOCALAPPDATA%\Treecer，其他平台为 ~/.local/share/Treecer。可用 TREECER_HOME 或 --home 覆盖。

catalog.sqlite 保存项目、工作区、会话绑定和位置；projects/<内部项目身份>/project.sqlite 保存各项目的任务和节点。本地 SQLite 使用事务及回滚日志，将跨项目分支移动和位置跟随作为一次提交。

0.1.2 首次访问时事务迁移 0.1.1 数据：原树根成为任务根下的主题，正文和状态保留，原位置转换到新路径。旧项目级主题归入新建 inbox 任务；名称已占用时使用 inbox (2) 等可区分名称。新版使用路径接口；升级前结束旧版本服务进程。

旧任务或迁移后的同父节点重名时，返回 MIGRATION_CONFLICT 并回滚该项目迁移，保留原数据；需要先确定这些条目的新名称。备份时关闭相关进程，完整复制数据目录和工作区标记；恢复后用 context show 核对位置。

## 错误处理

- SUDO_REQUIRED：核对目标后显式 sudo，或修正到当前任务路径。
- REVISION_CONFLICT：合并 current 中的最新内容，携带最新 revision。
- DUPLICATE_NAME：选择同父下不同名称，或更新已有节点。
- NODE_NOT_FOUND / TASK_NOT_FOUND / PROJECT_NOT_FOUND：核对路径及项目数据目录；节点错误会提供最近存在的祖先。
- TASK_REQUIRED / NODE_REQUIRED：选择任务或节点。
- INVALID_MOVE / ROOT_OPERATION：保持无环和任务根结构。
- TARGET_CHANGED：目标在本次解析后已移动，重新读取路径。
- MIGRATION_CONFLICT：原项目内容保留，先确定同名条目的新名称。
- STORE_BUSY：稍后重新读取并操作。

CLI 错误返回非零退出码；MCP 返回工具错误。
