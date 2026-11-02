# 快速开始

Treecer 让助手用名称和路径保存、深入并接续讨论。默认位置形如：

```text
Topic@Project: ~/方案讨论/方案选择$
```

## 安装

需要 Python 3.11+ 和已配置命令路径的 pipx。安装收到的发行包：

```text
pipx install ./treecer-0.1.2-py3-none-any.whl
```

也可从源码目录执行 `pipx install .`。安装后离开源码目录仍可调用：

```text
treecer --help
treecer setup
treecer doc
treecer doc quick-start --en
```

手册默认中文，--en 阅读英文；文档查询无需项目绑定，也不会创建数据库。setup 显示接入指南和随包 skill 的位置。

## 创建任务和讨论主题

进入工作区，例如名为 Project 的目录：

```text
treecer context show
treecer task add Topic
treecer node add 方案讨论
treecer focus "~/方案讨论"
treecer node add 方案选择 --note "待讨论：如何选择合适的方案？"
```

首次使用自动发现或登记项目。task add 创建任务并进入其根 `~`。node add 返回新节点的路径，保留当前位置；focus 明确进入某个节点。

CLI 中给 `"~/..."` 加引号，避免 shell 提前将 `~` 展开成电脑上的用户目录。路径属于 Treecer 的讨论空间。

```text
treecer focus "~/方案讨论/方案选择"
treecer context show
```

返回当前正文、祖先和直接孩子。默认提示始终表示保存的真实位置；操作对象通过单独的节点路径显示。节点身份由工具内部维护，日常操作使用路径。

## 记录结论并回溯

先读取节点，使用返回的 revision 更新。以下修订号 3 对应全新示例项目，实际以读取值为准：

```text
treecer node get "~/方案讨论/方案选择" --json
treecer node update "~/方案讨论/方案选择" --revision 3 --status 已解决 --note "用户已确定：按实际使用场景比较方案"
treecer focus ..
treecer children
```

状态为「讨论中、已解决、暂放、已取消」。子问题完成后，回父问题核对剩余问题，再找回暂放的旁枝。

## 查看和修改其他任务

绝对路径明确指定项目和任务：

```text
treecer context show "/Project/OtherTopic/方案讨论"
```

路径需已存在。跨任务查看直接允许，保留当前任务与位置。跨任务写入会停止并提示目标归属；确认目标后，用 `treecer sudo <原指令>` 或 --sudo 重试。sudo 只对当前这次写入生效。

## 接续

CLI 默认按工作区接续。不同聊天或终端可通过相同 --source 和 --session 恢复各自位置，或用 TREECER_SESSION 提供会话标识。task use 按名称切换任务并恢复该任务的位置。

MCP 用 scope.workspace 提供工作区、scope.session 提供稳定聊天标识；写入工具的 sudo=true 对应显式跨任务确认。完整参数和迁移说明见 `treecer doc reference`。
