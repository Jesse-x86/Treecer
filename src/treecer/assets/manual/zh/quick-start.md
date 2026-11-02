# 快速开始

Treecer 把讨论保存为可接续的树。助手随讨论维护节点，工具提供项目定位、局部导航和持久保存。

## 安装

需要 Python 3.11 或更新版本，以及已经配置好命令路径的 pipx。从源码目录安装：

```text
pipx install .
```

也可以安装拿到的发行包：

```text
pipx install ./treecer-0.1.1-py3-none-any.whl
```

安装后可以离开源码目录使用。先查看入口：

```text
treecer --help
treecer setup
treecer doc
treecer doc quick-start --en
```

`setup` 显示接入说明和随包 skill 的实际位置。`doc` 列出四个主题，提供主题名则读取正文，默认中文，`--en` 阅读英文。查询文档无需项目绑定，也不会创建项目数据。

## 第一次记录

进入想要跟踪讨论的工作区，执行：

```text
treecer context show
treecer task add Topic
treecer tree add 方案讨论
treecer node add 选择条件 --note "待讨论：何时触发方案比较？"
```

首次使用自动发现或登记项目，在工作区写入 `.treecer/project.json`，数据库保存在用户本地数据目录。任务创建后被选中，创建树后进入根节点；添加孩子时保持原讨论位置。

每次创建都会返回自动生成的 ID。以下用全新项目中的示例 ID `N2` 演示，实际操作使用返回值：

```text
treecer focus N2
treecer context show
```

如果工作区名为 Project，会看到：

```text
Topic@Project# 方案讨论/选择条件 [N2]
```

这行依次表示任务、项目、根到当前问题的路径和节点 ID。下面是当前节点正文及直接孩子。

## 记录结论，回到父问题

读取节点会返回 `revision`。假设当前值为 1：

```text
treecer node update N2 --revision 1 --status 已解决 --note "用户已确定：按当前消息需要触发方案比较"
treecer focus ..
treecer children
```

`focus ..` 返回父节点，`children` 显示仍可继续的分支。状态由明确更新决定，子问题完成后，助手回到父问题核对剩余内容。

## 恢复与多个聊天

重新在同一工作区调用 `context show` 可恢复 CLI 的位置。独立聊天或终端可使用各自稳定标识：

```text
treecer context show --source codex --session chat-123
```

后续调用使用相同 `--source` 和 `--session`，或通过 `TREECER_SESSION` 持续提供会话标识。跨来源访问同一项目时共享讨论内容，各会话保留自己的位置。

MCP 接入方式、工具参数和排障见 `treecer doc reference`。概念关系见 `treecer doc core-concept`；如何组织讨论见 `treecer doc workflow`。
